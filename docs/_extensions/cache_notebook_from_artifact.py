# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Populate the local jupyter-cache from the CI-executed tutorial notebook artifact.

Downloads the ``tutorial-notebook`` artifact produced by the Execute Tutorial Notebook
workflow for the current commit and caches it so that ``make html-with-artifact`` renders
the CI outputs locally without a live cluster. Uses only the standard library plus
``jupyter_cache``; no ``gh`` CLI is required.
"""

import json
import logging
import os
import re
import subprocess
import urllib.error
import urllib.request

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
    """Return stripped stdout of a git command run in this file's repo."""
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
        if exc.code in (401, 403):
            raise HelperError(
                "GitHub API rejected the token (HTTP "
                f"{exc.code}). Ensure GITHUB_TOKEN/GH_TOKEN is valid and has "
                "'actions:read' (repo read) scope."
            ) from exc
        raise


def _api_get_bytes(url, token):
    """GET an absolute URL and return raw bytes (used for the artifact zip download)."""
    request = urllib.request.Request(  # noqa: S310
        url,
        headers={**_API_HEADERS, "Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:  # noqa: S310
        return response.read()
