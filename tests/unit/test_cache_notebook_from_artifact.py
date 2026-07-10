# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the CI-artifact notebook cache helper."""

import importlib.util
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
