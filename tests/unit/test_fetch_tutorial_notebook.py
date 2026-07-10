# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the tutorial-notebook Sphinx fetch extension."""

import importlib.util
import json
import sys
import types
from pathlib import Path
from urllib.error import URLError

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "_extensions" / "fetch_tutorial_notebook.py"
)


def _nb_bytes(code_sources):
    """Build minimal notebook JSON bytes with the given code-cell sources."""
    cells = [
        {"cell_type": "code", "source": src, "metadata": {}, "outputs": [], "execution_count": None}
        for src in code_sources
    ]
    # Include a markdown cell to prove non-code cells are ignored by the matcher.
    cells.insert(0, {"cell_type": "markdown", "source": "# Title", "metadata": {}})
    return json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}).encode()


def _write_local_notebook(srcdir, code_sources):
    """Write a local tutorial.ipynb into srcdir and return its code sources."""
    (Path(srcdir) / "tutorial.ipynb").write_bytes(_nb_bytes(code_sources))
    return code_sources


def _set_rtd_env(monkeypatch, *, version_type="branch", commit="abc123"):
    monkeypatch.setenv("READTHEDOCS", "True")
    monkeypatch.setenv("READTHEDOCS_VERSION_TYPE", version_type)
    if commit is None:
        monkeypatch.delenv("READTHEDOCS_GIT_COMMIT_HASH", raising=False)
    else:
        monkeypatch.setenv("READTHEDOCS_GIT_COMMIT_HASH", commit)


def _load_module():
    """Load the extension module directly from its file path."""
    spec = importlib.util.spec_from_file_location("fetch_tutorial_notebook", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeConfig:
    def __init__(self):
        self.nb_execution_mode = "cache"
        self.nb_execution_cache_path = ""


class _FakeApp:
    def __init__(self, srcdir, outdir=None):
        self.srcdir = str(srcdir)
        # Mirror Sphinx: outdir defaults to a subdir of srcdir, but on Read the
        # Docs it lives outside the source tree entirely.
        self.outdir = str(outdir) if outdir is not None else str(Path(srcdir) / "_build")
        self.config = _FakeConfig()
        self.connected = []

    def connect(self, event, callback):
        self.connected.append((event, callback))


class _FakeResponse:
    def __init__(self, data):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture(name="module")
def module_fixture():
    return _load_module()


def test_not_on_rtd_returns_early(module, monkeypatch, tmp_path):
    monkeypatch.delenv("READTHEDOCS", raising=False)
    called = {"urlopen": False}

    def _fake_urlopen(*args, **kwargs):
        called["urlopen"] = True
        raise AssertionError("urlopen should not be called off RTD")

    monkeypatch.setattr(module.urllib.request, "urlopen", _fake_urlopen)
    app = _FakeApp(tmp_path)

    module._fetch_notebook(app)

    assert called["urlopen"] is False
    assert app.config.nb_execution_mode == "cache"


def test_download_and_cache_success(module, monkeypatch, tmp_path):
    monkeypatch.setenv("READTHEDOCS", "True")
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(b"notebook-bytes"),
    )

    recorded = {}

    class _FakeCache:
        def cache_notebook_file(self, path, uri, check_validity, overwrite):
            recorded["path"] = path
            recorded["uri"] = uri
            recorded["check_validity"] = check_validity
            recorded["overwrite"] = overwrite

    fake_jupyter_cache = types.ModuleType("jupyter_cache")
    fake_jupyter_cache.get_cache = lambda location: _FakeCache()
    monkeypatch.setitem(sys.modules, "jupyter_cache", fake_jupyter_cache)

    app = _FakeApp(tmp_path)

    module._fetch_notebook(app)

    assert recorded["uri"] == str(tmp_path / "tutorial.ipynb")
    assert recorded["overwrite"] is True
    assert recorded["check_validity"] is False
    assert app.config.nb_execution_mode == "cache"


def test_cache_written_to_myst_nb_read_location(module, monkeypatch, tmp_path):
    """Cache must be written where myst-nb reads it: outdir.parent/.jupyter_cache.

    Reproduces the RTD failure: when the build output dir lives outside the
    source tree (as on Read the Docs), writing the cache under srcdir means
    myst-nb never finds it and re-executes the notebook.
    """
    monkeypatch.setenv("READTHEDOCS", "True")
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(b"notebook-bytes"),
    )

    srcdir = tmp_path / "docs"
    srcdir.mkdir()
    outdir = tmp_path / "rtd_output" / "html"
    outdir.mkdir(parents=True)

    captured = {}

    class _FakeCache:
        def cache_notebook_file(self, path, uri, check_validity, overwrite):
            pass

    fake_jupyter_cache = types.ModuleType("jupyter_cache")

    def _get_cache(location):
        captured["location"] = location
        return _FakeCache()

    fake_jupyter_cache.get_cache = _get_cache
    monkeypatch.setitem(sys.modules, "jupyter_cache", fake_jupyter_cache)

    app = _FakeApp(srcdir, outdir=outdir)

    module._fetch_notebook(app)

    expected = str((Path(app.outdir).parent / ".jupyter_cache").resolve())
    assert captured["location"] == expected


def test_cache_honors_explicit_execution_cache_path(module, monkeypatch, tmp_path):
    """When nb_execution_cache_path is configured, the cache is written there."""
    monkeypatch.setenv("READTHEDOCS", "True")
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(b"notebook-bytes"),
    )

    configured = tmp_path / "custom_cache"

    captured = {}

    class _FakeCache:
        def cache_notebook_file(self, path, uri, check_validity, overwrite):
            pass

    fake_jupyter_cache = types.ModuleType("jupyter_cache")

    def _get_cache(location):
        captured["location"] = location
        return _FakeCache()

    fake_jupyter_cache.get_cache = _get_cache
    monkeypatch.setitem(sys.modules, "jupyter_cache", fake_jupyter_cache)

    app = _FakeApp(tmp_path / "docs")
    app.config.nb_execution_cache_path = str(configured)

    module._fetch_notebook(app)

    assert captured["location"] == str(configured)


def test_download_failure_sets_mode_off(module, monkeypatch, tmp_path):
    monkeypatch.setenv("READTHEDOCS", "True")

    def _raise(*a, **k):
        raise URLError("boom")

    monkeypatch.setattr(module.urllib.request, "urlopen", _raise)
    app = _FakeApp(tmp_path)

    module._fetch_notebook(app)

    assert app.config.nb_execution_mode == "off"


def test_cache_failure_sets_mode_off(module, monkeypatch, tmp_path):
    monkeypatch.setenv("READTHEDOCS", "True")
    monkeypatch.setattr(
        module.urllib.request,
        "urlopen",
        lambda *a, **k: _FakeResponse(b"notebook-bytes"),
    )

    fake_jupyter_cache = types.ModuleType("jupyter_cache")

    def _boom(location):
        raise RuntimeError("cache exploded")

    fake_jupyter_cache.get_cache = _boom
    monkeypatch.setitem(sys.modules, "jupyter_cache", fake_jupyter_cache)

    app = _FakeApp(tmp_path)

    module._fetch_notebook(app)

    assert app.config.nb_execution_mode == "off"


def test_code_cells_match_true_ignores_markdown_and_outputs(module, tmp_path):
    local = _write_local_notebook(tmp_path, ["echo one", "echo two"])
    candidate = _nb_bytes(["echo one", "echo two"])
    assert module._code_cells_match(candidate, Path(tmp_path) / "tutorial.ipynb") is True


def test_code_cells_match_false_on_different_code(module, tmp_path):
    _write_local_notebook(tmp_path, ["echo one"])
    candidate = _nb_bytes(["echo DIFFERENT"])
    assert module._code_cells_match(candidate, Path(tmp_path) / "tutorial.ipynb") is False


def test_code_cells_match_false_on_bad_json(module, tmp_path):
    _write_local_notebook(tmp_path, ["echo one"])
    assert module._code_cells_match(b"not json", Path(tmp_path) / "tutorial.ipynb") is False


def test_code_cells_match_normalizes_list_sources(module, tmp_path):
    (Path(tmp_path) / "tutorial.ipynb").write_bytes(
        json.dumps(
            {"cells": [{"cell_type": "code", "source": ["echo ", "one"]}], "nbformat": 4, "nbformat_minor": 5}
        ).encode()
    )
    candidate = _nb_bytes(["echo one"])
    assert module._code_cells_match(candidate, Path(tmp_path) / "tutorial.ipynb") is True


def test_setup_registers_hook(module, tmp_path):
    app = _FakeApp(tmp_path)

    result = module.setup(app)

    assert ("builder-inited", module._fetch_notebook) in app.connected
    assert result["parallel_read_safe"] is True
    assert result["parallel_write_safe"] is True


def test_wait_returns_notebook_when_commit_matches_first_try(module, monkeypatch):
    monkeypatch.setattr(module, "_WAIT_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(module, "_POLL_INTERVAL_SECONDS", 0)
    calls = []

    def _fake_download(url):
        calls.append(url)
        if url == module._COMMIT_URL:
            return b"target-sha\n"
        return b"NOTEBOOK"

    monkeypatch.setattr(module, "_download_bytes", _fake_download)
    result = module._wait_for_fresh_notebook("target-sha")
    assert result == b"NOTEBOOK"


def test_wait_retries_until_commit_matches(module, monkeypatch):
    monkeypatch.setattr(module, "_WAIT_TIMEOUT_SECONDS", 5)
    monkeypatch.setattr(module, "_POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    seq = [b"old-sha\n", None, b"target-sha\n"]  # stale, then 404, then match

    def _fake_download(url):
        if url == module._COMMIT_URL:
            return seq.pop(0)
        return b"NOTEBOOK"

    monkeypatch.setattr(module, "_download_bytes", _fake_download)
    result = module._wait_for_fresh_notebook("target-sha")
    assert result == b"NOTEBOOK"
    assert seq == []


def test_wait_times_out_returns_none(module, monkeypatch):
    # Timeout budget of 0 means the loop runs once then gives up.
    monkeypatch.setattr(module, "_WAIT_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(module, "_POLL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(module.time, "sleep", lambda s: None)
    monkeypatch.setattr(module, "_download_bytes", lambda url: b"never-matches\n")
    assert module._wait_for_fresh_notebook("target-sha") is None
