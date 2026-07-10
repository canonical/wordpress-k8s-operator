# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Sphinx extension to fetch pre-executed tutorial notebook from GitHub releases."""

import json
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


def _fetch_notebook(app):
    """Download pre-executed tutorial notebook from GitHub releases.

    Populates the jupyter-cache so that myst-nb finds a cache hit for tutorial.ipynb.
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
            uri=str(Path(app.srcdir) / "tutorial.ipynb"),
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
