# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Sphinx extension to fetch pre-executed tutorial notebook from GitHub releases."""

import logging
import os
import tempfile
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

    Populates the jupyter-cache so that myst-nb finds a cache hit for tutorial.md
    and renders the pre-executed outputs without re-running the notebook.

    If the download or caching fails, the build continues without cached outputs
    (graceful degradation).
    """
    if not os.environ.get("READTHEDOCS"):
        return

    logger.info("Fetching pre-executed tutorial notebook from %s", _DOWNLOAD_URL)

    try:
        with urllib.request.urlopen(_DOWNLOAD_URL, timeout=60) as response:  # noqa: S310
            nb_bytes = response.read()
    except (URLError, OSError) as exc:
        logger.warning(
            "Failed to download tutorial notebook from %s: %s. "
            "Tutorial will render without execution outputs.",
            _DOWNLOAD_URL,
            exc,
        )
        app.config.nb_execution_mode = "off"
        return

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".ipynb", delete=False) as f:
            f.write(nb_bytes)
            tmp_path = Path(f.name)

        from jupyter_cache import get_cache  # noqa: PLC0415

        cache = get_cache(str(Path(app.srcdir) / ".jupyter_cache"))
        cache.cache_notebook_file(
            path=str(tmp_path),
            uri=str(Path(app.srcdir) / "tutorial.md"),
            check_validity=False,
            overwrite=True,
        )
        logger.info("Successfully cached tutorial notebook from %s", _DOWNLOAD_URL)
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
