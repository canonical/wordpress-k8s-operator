# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the CI-artifact notebook cache helper."""

import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "_extensions"
    / "cache_notebook_from_artifact.py"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("cache_notebook_from_artifact", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="module")
def module_fixture():
    return _load_module()


def test_resolve_token_prefers_github_token(module, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "gh_primary")
    monkeypatch.setenv("GH_TOKEN", "gh_secondary")
    assert module._resolve_token() == "gh_primary"


def test_resolve_token_falls_back_to_gh_token(module, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GH_TOKEN", "gh_secondary")
    assert module._resolve_token() == "gh_secondary"


def test_resolve_token_missing_raises(module, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    with pytest.raises(module.HelperError):
        module._resolve_token()


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:canonical/wordpress-k8s-operator.git",
        "https://github.com/canonical/wordpress-k8s-operator.git",
        "https://github.com/canonical/wordpress-k8s-operator",
    ],
)
def test_resolve_repo_parses_forms(module, monkeypatch, url):
    monkeypatch.setattr(module, "_git", lambda *args: url)
    assert module._resolve_repo() == ("canonical", "wordpress-k8s-operator")


def test_resolve_repo_bad_url_raises(module, monkeypatch):
    monkeypatch.setattr(module, "_git", lambda *args: "not-a-remote")
    with pytest.raises(module.HelperError):
        module._resolve_repo()


def _nb_bytes(code_sources):
    cells = [{"cell_type": "markdown", "source": "# Title", "metadata": {}}]
    cells += [
        {"cell_type": "code", "source": s, "metadata": {}, "outputs": [], "execution_count": None}
        for s in code_sources
    ]
    return json.dumps({"cells": cells, "metadata": {}, "nbformat": 4, "nbformat_minor": 5}).encode()


def _zip_with(name, data):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(name, data)
    return buf.getvalue()


def test_extract_notebook_reads_ipynb(module):
    payload = _nb_bytes(["echo one"])
    zip_bytes = _zip_with("tutorial.ipynb", payload)
    assert module._extract_notebook(zip_bytes) == payload


def test_find_successful_run_returns_id(module, monkeypatch):
    monkeypatch.setattr(
        module, "_api_get_json", lambda path, token: {"workflow_runs": [{"id": 4242}]}
    )
    assert module._find_successful_run("o", "r", "sha", "t") == 4242


def test_find_successful_run_none_raises(module, monkeypatch):
    monkeypatch.setattr(module, "_api_get_json", lambda path, token: {"workflow_runs": []})
    with pytest.raises(module.HelperError):
        module._find_successful_run("o", "r", "sha", "t")


@pytest.mark.parametrize("code", [404, 422])
def test_assert_commit_pushed_not_found_raises(module, monkeypatch, code):
    def _raise(path, token):
        raise module.urllib.error.HTTPError(path, code, "err", {}, None)

    monkeypatch.setattr(module, "_api_get_json", _raise)
    with pytest.raises(module.HelperError):
        module._assert_commit_pushed("o", "r", "sha", "t")


def test_assert_commit_pushed_other_error_reraises(module, monkeypatch):
    def _raise(path, token):
        raise module.urllib.error.HTTPError(path, 500, "boom", {}, None)

    monkeypatch.setattr(module, "_api_get_json", _raise)
    with pytest.raises(module.urllib.error.HTTPError):
        module._assert_commit_pushed("o", "r", "sha", "t")


def test_populate_cache_mismatch_raises(module, tmp_path):
    source = tmp_path / "tutorial.ipynb"
    source.write_bytes(_nb_bytes(["echo one"]))
    with pytest.raises(module.HelperError):
        module._populate_cache(_nb_bytes(["echo DIFFERENT"]), source, tmp_path / ".jupyter_cache")


def test_populate_cache_success_calls_cache(module, monkeypatch, tmp_path):
    source = tmp_path / "tutorial.ipynb"
    source.write_bytes(_nb_bytes(["echo one"]))
    recorded = {}

    class _FakeCache:
        def cache_notebook_file(self, path, uri, check_validity, overwrite):
            recorded["uri"] = uri
            recorded["overwrite"] = overwrite
            recorded["check_validity"] = check_validity

    fake_jc = type(sys)("jupyter_cache")
    fake_jc.get_cache = lambda cache_dir: _FakeCache()
    monkeypatch.setitem(sys.modules, "jupyter_cache", fake_jc)

    module._populate_cache(_nb_bytes(["echo one"]), source, tmp_path / ".jupyter_cache")

    assert recorded["uri"] == str(source.resolve())
    assert recorded["overwrite"] is True
    assert recorded["check_validity"] is False


def test_strip_auth_redirect_drops_authorization(module):
    handler = module._StripAuthRedirect()
    req = module.urllib.request.Request(
        "https://api.github.com/x",
        headers={"Authorization": "Bearer secret", "Accept": "application/vnd.github+json"},
    )
    new = handler.redirect_request(req, None, 302, "Found", {}, "https://storage.example.com/y")
    assert new is not None
    assert not any(k.lower() == "authorization" for k in new.headers)
    assert any(k.lower() == "accept" for k in new.headers)
