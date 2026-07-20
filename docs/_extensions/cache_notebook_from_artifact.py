# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Populate the local jupyter-cache from the CI-executed tutorial notebook artifact.

Downloads the ``tutorial-notebook`` artifact produced by the Execute Tutorial Notebook
workflow for the current commit and caches it so that ``make html-with-artifact`` renders
the CI outputs locally without a live cluster. Uses only the standard library plus
``jupyter_cache``; no ``gh`` CLI is required.
"""

import argparse
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

logger = logging.getLogger(__name__)

_API_BASE = "https://api.github.com"
_WORKFLOW_FILE = "execute_tutorial_notebook.yaml"
_ARTIFACT_NAME = "tutorial-notebook"
_SOURCE_NOTEBOOK = "tutorial.ipynb"
_API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class HelperError(Exception):
    """A user-facing error; main() prints the message and exits non-zero."""


def _git(*args):
    """Return stripped stdout of a git command (run from the current working directory)."""
    result = subprocess.run(
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _resolve_token():
    """Return a GitHub token from GITHUB_TOKEN or GH_TOKEN, else raise HelperError."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise HelperError(
            "No GitHub token found. Export a token with 'actions:read' (repo read) scope, "
            "e.g. `export GITHUB_TOKEN=<token>`, then re-run. This is needed to look up and "
            "download the CI-executed notebook artifact."
        )
    return token


def _resolve_repo():
    """Return (owner, repo) parsed from the origin remote URL, or raise HelperError."""
    url = _git("config", "--get", "remote.origin.url")
    match = re.search(r"github\.com[:/]([^/]+)/(.+?)(?:\.git)?$", url)
    if not match:
        raise HelperError(f"Could not parse owner/repo from remote.origin.url: {url!r}")
    return match.group(1), match.group(2)


def _current_commit():
    """Return the current HEAD commit SHA."""
    return _git("rev-parse", "HEAD")


def _api_get_json(path, token):
    """GET a GitHub API path and return parsed JSON, mapping auth errors to HelperError."""
    request = urllib.request.Request(  # noqa: S310
        f"{_API_BASE}{path}",
        headers={**_API_HEADERS, "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 429) and (
            exc.headers.get("X-RateLimit-Remaining") == "0" or exc.headers.get("Retry-After")
        ):
            retry_after = exc.headers.get("Retry-After")
            msg = f"GitHub API rate limit reached (HTTP {exc.code}). Wait and re-run"
            if retry_after:
                msg += f"; retry after {retry_after} seconds."
            else:
                msg += "."
            raise HelperError(msg) from exc
        if exc.code in (401, 403):
            raise HelperError(
                "GitHub API rejected the token (HTTP "
                f"{exc.code}). Ensure GITHUB_TOKEN/GH_TOKEN is valid and has "
                "'actions:read' (repo read) scope."
            ) from exc
        raise


class _StripAuthRedirect(urllib.request.HTTPRedirectHandler):
    """Redirect handler that drops the Authorization header on redirect.

    GitHub's artifact download endpoint returns a 302 to a pre-signed storage
    URL that must be fetched without the GitHub token; sending it makes the
    storage host reject the request with HTTP 401.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Build the redirected request without the Authorization header."""
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            for key in list(new.headers):
                if key.lower() == "authorization":
                    del new.headers[key]
        return new


def _api_get_bytes(url, token):
    """GET an absolute URL and return raw bytes (used for the artifact zip download).

    Follows GitHub's 302 redirect to signed storage, dropping the Authorization
    header on the redirect so the storage host does not reject the request (401).
    """
    request = urllib.request.Request(  # noqa: S310
        url,
        headers={**_API_HEADERS, "Authorization": f"Bearer {token}"},
    )
    opener = urllib.request.build_opener(_StripAuthRedirect())
    try:
        with opener.open(request, timeout=120) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 410:
            raise HelperError(
                "The CI artifact for this commit has expired (GitHub deletes artifacts after "
                "~90 days). Push a fresh commit and wait for the Execute Tutorial Notebook "
                "workflow, then re-run."
            ) from exc
        if exc.code == 404:
            raise HelperError(
                "The CI artifact is no longer available. Push a fresh commit and wait for the "
                "Execute Tutorial Notebook workflow, then re-run."
            ) from exc
        raise


def _assert_commit_pushed(owner, repo, commit, token):
    """Raise HelperError if the commit is not present on the remote (HTTP 404 or 422)."""
    try:
        _api_get_json(f"/repos/{owner}/{repo}/commits/{commit}", token)
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 422):
            raise HelperError(
                f"Commit {commit} isn't pushed to the remote yet. Push it and wait for the "
                "Execute Tutorial Notebook workflow to finish, then re-run."
            ) from exc
        raise


def _find_successful_run(owner, repo, commit, token):
    """Return the id of the latest successful Execute run for this exact commit."""
    path = (
        f"/repos/{owner}/{repo}/actions/workflows/{_WORKFLOW_FILE}/runs"
        f"?head_sha={commit}&status=success&per_page=1"
    )
    runs = _api_get_json(path, token).get("workflow_runs", [])
    if not runs:
        raise HelperError(
            f"No successful Execute Tutorial Notebook run for commit {commit} yet. "
            "Wait for the workflow to finish (or check it didn't fail), then re-run."
        )
    return runs[0]["id"]


def _artifact_download_url(owner, repo, run_id, token):
    """Return the archive_download_url of the tutorial-notebook artifact for a run."""
    path = f"/repos/{owner}/{repo}/actions/runs/{run_id}/artifacts?per_page=100"
    artifacts = _api_get_json(path, token).get("artifacts", [])
    for artifact in artifacts:
        if artifact.get("name") == _ARTIFACT_NAME:
            return artifact["archive_download_url"]
    raise HelperError(
        f"Run {run_id} has no '{_ARTIFACT_NAME}' artifact. The workflow may still be "
        "running or failed to upload it; wait and re-run."
    )


def _extract_notebook(zip_bytes):
    """Return the tutorial.ipynb bytes from the artifact zip."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        preferred = None
        fallback = None
        for name in archive.namelist():
            if name.endswith(".ipynb"):
                if Path(name).name == _SOURCE_NOTEBOOK:
                    preferred = name
                    break
                if fallback is None:
                    fallback = name
        if preferred:
            return archive.read(preferred)
        if fallback:
            return archive.read(fallback)
    raise HelperError(f"No .ipynb found inside the '{_ARTIFACT_NAME}' artifact.")


def _load_matcher():
    """Return _code_cells_match from the sibling fetch extension module."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from fetch_tutorial_notebook import _code_cells_match  # noqa: PLC0415

    return _code_cells_match


def _populate_cache(nb_bytes, source_path, cache_dir):
    """Verify code cells match the source, then cache the notebook bytes."""
    source_path = Path(source_path)
    # Match guard: compare only code-cell sources (what myst-nb renders); a metadata-only
    # drift causes a cache MISS → loud --fail-on-warning failure, not a silent stale render.
    if not _load_matcher()(nb_bytes, source_path):
        raise HelperError(
            f"CI artifact code cells don't match {source_path}. The notebook changed since "
            "this run; push the change and wait for a fresh run, then re-run."
        )

    from jupyter_cache import get_cache  # noqa: PLC0415

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as handle:
            handle.write(nb_bytes)
            tmp_path = Path(handle.name)
        get_cache(str(cache_dir)).cache_notebook_file(
            path=str(tmp_path),
            uri=str(source_path.resolve()),
            check_validity=False,
            overwrite=True,
        )
        logger.info("Cached CI notebook outputs into %s", cache_dir)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def main(argv=None):
    """Resolve the CI artifact for HEAD and populate the jupyter-cache."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=_SOURCE_NOTEBOOK)
    parser.add_argument("--cache-dir", default=".jupyter_cache")
    args = parser.parse_args(argv)

    try:
        token = _resolve_token()
        owner, repo = _resolve_repo()
        commit = _current_commit()
        logger.info("Looking up CI artifact for %s/%s @ %s", owner, repo, commit)
        _assert_commit_pushed(owner, repo, commit, token)
        run_id = _find_successful_run(owner, repo, commit, token)
        url = _artifact_download_url(owner, repo, run_id, token)
        nb_bytes = _extract_notebook(_api_get_bytes(url, token))
        _populate_cache(nb_bytes, args.source, args.cache_dir)
    except HelperError as exc:
        logger.error("error: %s", exc)
        return 1
    except (urllib.error.URLError, OSError) as exc:
        logger.error(
            "error: network/API request failed: %s. Check your connection and GitHub status, "
            "then re-run.",
            exc,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
