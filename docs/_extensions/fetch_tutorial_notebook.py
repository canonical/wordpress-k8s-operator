# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Sphinx extension to fetch pre-executed tutorial notebook from GitHub releases."""

import json
import logging
import os
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.error import URLError

logger = logging.getLogger(__name__)

_GITHUB_REPO = "canonical/wordpress-k8s-operator"
_RELEASE_TAG = "docs-latest"
_ASSET_NAME = "tutorial.ipynb"
_DOWNLOAD_URL = (
    f"https://github.com/{_GITHUB_REPO}/releases/download/{_RELEASE_TAG}/{_ASSET_NAME}"
)
_COMMIT_ASSET_NAME = "commit.txt"
_COMMIT_URL = (
    f"https://github.com/{_GITHUB_REPO}/releases/download/{_RELEASE_TAG}/{_COMMIT_ASSET_NAME}"
)
_POLL_INTERVAL_SECONDS = 15
_WAIT_TIMEOUT_SECONDS = 180


def _code_cell_sources(nb_bytes):
    """Return the ordered list of normalized code-cell sources, or None on error."""
    try:
        nb = json.loads(nb_bytes)
        sources = []
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            source = cell.get("source", "")
            if isinstance(source, list):
                source = "".join(source)
            sources.append(source)
        return sources
    except (ValueError, TypeError):
        return None


def _code_cells_match(candidate_bytes, local_path):
    """True iff candidate and local notebook have identical ordered code cells."""
    candidate = _code_cell_sources(candidate_bytes)
    try:
        local = _code_cell_sources(local_path.read_bytes())
    except OSError:
        return False
    return candidate is not None and candidate == local


def _download_bytes(url):
    """Download bytes from url, or return None on network error / missing asset."""
    try:
        with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310
            return response.read()
    except (URLError, OSError):
        return None


def _wait_for_fresh_notebook(commit):
    """Poll commit.txt until it matches `commit`, then return the notebook bytes.

    Returns None if the release does not become fresh within the timeout. This
    covers the merge-time race where the publish workflow has not yet replaced
    docs-latest for the commit Read the Docs is currently building.
    """
    deadline = time.monotonic() + _WAIT_TIMEOUT_SECONDS
    while True:
        published = _download_bytes(_COMMIT_URL)
        if published is not None and published.decode(errors="replace").strip() == commit:
            return _download_bytes(_DOWNLOAD_URL)
        if time.monotonic() >= deadline:
            return None
        time.sleep(_POLL_INTERVAL_SECONDS)


def _fetch_notebook(app):
    """Download pre-executed tutorial notebook from GitHub releases.

    Populates the jupyter-cache so that myst-nb finds a cache hit for tutorial.ipynb
    and renders the pre-executed outputs without re-running the notebook.

    If the download or caching fails, the build continues without cached outputs
    (graceful degradation).
    """
    if not os.environ.get("READTHEDOCS"):
        return

    version_type = os.environ.get("READTHEDOCS_VERSION_TYPE", "")
    commit = os.environ.get("READTHEDOCS_GIT_COMMIT_HASH", "")

    if version_type != "external" and commit:
        logger.info("Waiting for docs-latest to match commit %s", commit)
        nb_bytes = _wait_for_fresh_notebook(commit)
    else:
        logger.info("Fetching tutorial notebook from %s", _DOWNLOAD_URL)
        nb_bytes = _download_bytes(_DOWNLOAD_URL)

    if nb_bytes is None:
        logger.warning(
            "No fresh tutorial notebook available. Rendering without execution outputs."
        )
        app.config.nb_execution_mode = "off"
        return

    local_notebook = Path(app.srcdir) / "tutorial.ipynb"
    if not _code_cells_match(nb_bytes, local_notebook):
        logger.warning(
            "Published tutorial notebook does not match local code cells. "
            "Rendering without execution outputs."
        )
        app.config.nb_execution_mode = "off"
        return

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as f:
            f.write(nb_bytes)
            tmp_path = Path(f.name)

        from jupyter_cache import get_cache  # noqa: PLC0415

        # myst-nb reads its cache from nb_execution_cache_path when configured,
        # otherwise from `<outdir>/../.jupyter_cache` (see myst_nb.sphinx_ext).
        # We must populate that exact location: on Read the Docs the build output
        # lives outside the source tree, so writing under srcdir would be silently
        # ignored and the notebook re-executed.
        configured_cache_path = getattr(app.config, "nb_execution_cache_path", "")
        if configured_cache_path:
            cache_dir = configured_cache_path
        else:
            cache_dir = str((Path(app.outdir).parent / ".jupyter_cache").resolve())

        cache = get_cache(cache_dir)
        cache.cache_notebook_file(
            path=str(tmp_path),
            uri=str(local_notebook),
            check_validity=False,
            overwrite=True,
        )
        logger.info("Successfully cached tutorial notebook")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to cache tutorial notebook: %s. "
            "Tutorial will render without execution outputs.",
            exc,
        )
        app.config.nb_execution_mode = "off"
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def setup(app):
    """Register the extension with Sphinx."""
    app.connect("builder-inited", _fetch_notebook)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
