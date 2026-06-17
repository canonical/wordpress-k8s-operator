# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Sphinx extension to fetch pre-executed tutorial notebook from GitHub releases."""

import logging
import os
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


def _fetch_notebook(app):
    """Download pre-executed tutorial notebook from GitHub releases.

    Places the notebook under jupyter_execute/ so that myst-nb picks it up as
    a cached execution result. If the source inputs match, the outputs from the
    downloaded notebook are used when rendering the tutorial page.

    If the download fails, the build continues without cached outputs (graceful
    degradation).
    """
    if not os.environ.get("READTHEDOCS"):
        return

    src_dir = Path(app.srcdir)
    cache_dir = src_dir / "jupyter_execute"
    cache_dir.mkdir(parents=True, exist_ok=True)
    notebook_dest = cache_dir / "tutorial.ipynb"

    logger.info("Fetching pre-executed tutorial notebook from %s", _DOWNLOAD_URL)

    try:
        with urllib.request.urlopen(_DOWNLOAD_URL, timeout=60) as response:  # noqa: S310
            notebook_dest.write_bytes(response.read())
    except (URLError, OSError) as exc:
        logger.warning(
            "Failed to download tutorial notebook from %s: %s. "
            "Tutorial will render without execution outputs.",
            _DOWNLOAD_URL,
            exc,
        )
        app.config.nb_execution_mode = "off"
        return

    logger.info("Successfully fetched tutorial notebook to %s", notebook_dest)


def setup(app):
    """Register the extension with Sphinx."""
    app.connect("builder-inited", _fetch_notebook)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
