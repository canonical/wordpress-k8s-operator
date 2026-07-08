# Merge main and restore the Jupyter notebook tutorial — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge `origin/main` into `fix/polish-tutorial.ipynb`, keep the Jupyter notebook as the tutorial's single source of truth, restore the notebook build infrastructure the merge removes, and add unit tests for the Read the Docs fetch extension.

**Architecture:** The branch carries a notebook-based tutorial (`docs/tutorial.ipynb` + a Sphinx extension that fetches a pre-executed notebook on RTD). `main`'s PR #369 rebuilt the RTD docs setup and, as a side effect, deleted that feature and restored `docs/tutorial.md`. We merge main (adopting its new RTD base), then re-apply the notebook pieces on top of main's rewritten `conf.py`, `Makefile`, and `requirements.txt`, and drop `tutorial.md`. Unit tests exercise the extension's env-var branches locally without a cluster.

**Tech Stack:** Git (merge conflict resolution), Sphinx + myst-nb, Python 3, pytest (`tox -e unit`), `uv` runner.

## Global Constraints

- Notebook (`docs/tutorial.ipynb`) is the single source of truth. `docs/tutorial.md` must NOT exist after this work.
- Adopt main's RTD base verbatim except for the notebook additions specified here. Do not revert unrelated #369 changes.
- Directory layout is main's: static assets in `docs/_static/`, templates in `docs/_templates/`, dev tooling in `docs/_dev/`. Do NOT reintroduce `docs/.sphinx/`.
- Notebook dependency pins (copied verbatim): `myst-nb==1.1.2`, `bash_kernel==0.10.0`.
- The merge is a single merge commit. Tasks 2's resolution steps all land in that one commit.
- Do not modify charm source (`src/`) or unrelated workflows.
- Coverage gate `fail_under = 90` is scoped to charm `src/`; the new test file does not affect it.

---

### Task 1: Unit tests for the RTD fetch extension

Write these tests first, against the module as it currently exists on the branch (`docs/_extensions/fetch_tutorial_notebook.py`). The merge in Task 2 keeps this module unchanged, so the tests remain valid afterward. The module imports `jupyter_cache` lazily inside the function, and only stdlib at module top-level, so the test loads it by path and mocks at the `urllib` / `jupyter_cache` boundary — no docs dependencies need to be installed.

**Files:**
- Create: `tests/unit/test_fetch_tutorial_notebook.py`
- Reference (do not modify): `docs/_extensions/fetch_tutorial_notebook.py`

**Interfaces:**
- Consumes from the module under test:
  - `_fetch_notebook(app)` — reads `os.environ["READTHEDOCS"]`; on RTD downloads `https://github.com/canonical/wordpress-k8s-operator/releases/download/docs-latest/tutorial.ipynb` via `urllib.request.urlopen`, writes it to a temp file, and calls `jupyter_cache.get_cache(...).cache_notebook_file(path=..., uri=<srcdir>/tutorial.ipynb, check_validity=False, overwrite=True)`. On download or cache failure it sets `app.config.nb_execution_mode = "off"`. Off-RTD it returns immediately.
  - `setup(app)` — calls `app.connect("builder-inited", _fetch_notebook)` and returns `{"version": "0.1", "parallel_read_safe": True, "parallel_write_safe": True}`.
- Produces: none (test-only).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_fetch_tutorial_notebook.py` with this exact content:

```python
# Copyright 2026 Canonical Ltd.
# See LICENSE file for licensing details.

"""Unit tests for the tutorial-notebook Sphinx fetch extension."""

import importlib.util
import sys
import types
from pathlib import Path
from urllib.error import URLError

import pytest

_MODULE_PATH = (
    Path(__file__).resolve().parents[2] / "docs" / "_extensions" / "fetch_tutorial_notebook.py"
)


def _load_module():
    """Load the extension module directly from its file path."""
    spec = importlib.util.spec_from_file_location("fetch_tutorial_notebook", _MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeConfig:
    def __init__(self):
        self.nb_execution_mode = "cache"


class _FakeApp:
    def __init__(self, srcdir):
        self.srcdir = str(srcdir)
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


def test_setup_registers_hook(module, tmp_path):
    app = _FakeApp(tmp_path)

    result = module.setup(app)

    assert ("builder-inited", module._fetch_notebook) in app.connected
    assert result["parallel_read_safe"] is True
    assert result["parallel_write_safe"] is True
```

- [ ] **Step 2: Run the tests to verify they pass**

The module already exists on the branch, so these should pass immediately (this is characterization of existing behavior, not red-then-green).

Run: `tox -e unit -- tests/unit/test_fetch_tutorial_notebook.py -v`
Expected: 5 passed. If `tox` is unavailable, run: `python -m pytest tests/unit/test_fetch_tutorial_notebook.py -v`

- [ ] **Step 3: Confirm the file paths resolve**

`parents[2]` from `tests/unit/test_fetch_tutorial_notebook.py` is the repo root, so `_MODULE_PATH` points at `docs/_extensions/fetch_tutorial_notebook.py`. If the tests error with `FileNotFoundError`, verify the module path before proceeding.

Run: `python -c "from pathlib import Path; p=Path('tests/unit/test_fetch_tutorial_notebook.py').resolve().parents[2]/'docs/_extensions/fetch_tutorial_notebook.py'; print(p, p.exists())"`
Expected: prints the absolute path and `True`.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_fetch_tutorial_notebook.py
git commit -m "test: add unit tests for tutorial notebook fetch extension

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
```

---

### Task 2: Merge main and resolve conflicts

Perform the merge and resolve the four git-flagged conflicts plus the two silent drops (`requirements.txt` notebook deps). This all lands in one merge commit.

**Files:**
- Modify (conflict, take main + notebook edits): `docs/conf.py`
- Modify (conflict, take main + notebook edits): `docs/Makefile`
- Keep ours (conflict modify/delete): `docs/_extensions/fetch_tutorial_notebook.py`
- Delete (conflict delete/modify): `docs/tutorial.md`
- Modify (silent drop, re-add deps): `docs/requirements.txt`

**Interfaces:**
- Consumes: `docs/_extensions/fetch_tutorial_notebook.py` (the module tested in Task 1), referenced by `conf.py` via `sys.path` + the `fetch_tutorial_notebook` extension entry.
- Produces: a merged working tree where `make html-with-exec` executes the notebook, `make html` builds without executing, and RTD builds use the fetch extension + `nb_execution_mode = "cache"`.

- [ ] **Step 1: Confirm clean starting state**

Run: `git status --short && git branch --show-current`
Expected: clean working tree, on `fix/polish-tutorial.ipynb`.

- [ ] **Step 2: Start the merge (expect conflicts)**

Run: `git fetch origin && git merge --no-ff origin/main`
Expected: merge stops with conflicts in exactly these four files:
```
docs/Makefile
docs/_extensions/fetch_tutorial_notebook.py
docs/conf.py
docs/tutorial.md
```

Verify: `git diff --name-only --diff-filter=U` lists those four. If more files conflict, STOP and re-investigate before continuing.

- [ ] **Step 3: Keep the fetch extension (ours), drop tutorial.md**

```bash
git add docs/_extensions/fetch_tutorial_notebook.py
git rm docs/tutorial.md
```

Verify: `git status --short docs/_extensions/fetch_tutorial_notebook.py docs/tutorial.md`
Expected: extension staged (no `U`); `tutorial.md` shows `D` (deleted/staged).

- [ ] **Step 4: Take main's conf.py as the base for resolution**

```bash
git checkout --theirs -- docs/conf.py
git add docs/conf.py
```

This adopts main's rewritten `conf.py` (new `_static`/`_templates` paths, CDN css/js, rediraffe). The notebook edits are applied in the next steps.

- [ ] **Step 5: Add the extension path import to conf.py**

Edit `docs/conf.py`. Replace:

```python
import datetime
import os
import yaml
```

with:

```python
import datetime
import os
import sys
import yaml

sys.path.insert(0, os.path.abspath("_extensions"))
```

- [ ] **Step 6: Register the fetch extension in conf.py**

Edit `docs/conf.py`. Replace:

```python
    "sphinxcontrib.mermaid",
]
```

with:

```python
    "sphinxcontrib.mermaid",
    "fetch_tutorial_notebook",
]
```

- [ ] **Step 7: Add jupyter excludes and nb settings to conf.py**

Edit `docs/conf.py`. Replace:

```python
exclude_patterns = [
    "doc-cheat-sheet*",
    ".venv*",
]

# Adds custom CSS files, located under 'html_static_path'
```

with:

```python
exclude_patterns = [
    "doc-cheat-sheet*",
    ".venv*",
    "jupyter_execute",
    ".jupyter_cache",
]

nb_execution_mode = "cache"
nb_execution_timeout = 3600
nb_execution_show_tb = True
nb_execution_raise_on_error = True

# Adds custom CSS files, located under 'html_static_path'
```

- [ ] **Step 8: Append the myst_nb compatibility setup() to conf.py**

Edit `docs/conf.py`. Replace:

```python
    'charmed-mysql': ("https://canonical-charmed-mysql.readthedocs-hosted.com/8.0/", None),
}
```

with:

```python
    'charmed-mysql': ("https://canonical-charmed-mysql.readthedocs-hosted.com/8.0/", None),
}


def setup(app):
    """Set up myst_nb with compatibility fix for canonical_sphinx.

    canonical_sphinx loads myst_parser which registers all myst-related roles,
    directives, transforms, and config values. When myst_nb subsequently calls
    setup_myst_parser, it tries to re-register everything, causing conflicts.
    We work around this by making setup_myst_parser a no-op before loading myst_nb.
    """
    import myst_parser.sphinx_ext.main as myst_main

    # canonical_sphinx already called setup_sphinx (via myst_parser), so all myst_parser
    # roles, directives, transforms, and config values are already registered.
    # Make it a no-op so myst_nb doesn't re-register them.
    myst_main.setup_sphinx = lambda app, load_parser=False: None

    app.setup_extension("myst_nb")
```

- [ ] **Step 9: Stage and syntax-check conf.py**

```bash
git add docs/conf.py
python -c "import ast; ast.parse(open('docs/conf.py').read()); print('conf.py OK')"
```
Expected: `conf.py OK`. Also confirm the notebook markers are present:

Run: `grep -nE 'fetch_tutorial_notebook|nb_execution_mode|_extensions|def setup' docs/conf.py`
Expected: matches for the sys.path insert, the extension entry, `nb_execution_mode = "cache"`, and `def setup(app)`.

- [ ] **Step 10: Take main's Makefile as the base for resolution**

```bash
git checkout --theirs -- docs/Makefile
git add docs/Makefile
```

Main's Makefile uses variables `DEV_DIR`, `DOCS_VENVDIR`, `DOCS_VENV`, `DOCS_SOURCEDIR`, `DOCS_BUILDDIR`, `SPHINX_BUILD`, `SPHINX_OPTS`, `SPHINX_HOST`, `SPHINX_PORT`, `CHECK_PATH`. The notebook additions below use those names.

- [ ] **Step 11: Add notebook help lines to the Makefile**

Edit `docs/Makefile`. Replace:

```
	@echo "* only build:                                make html"
```

with:

```
	@echo "* only build:                                make html"
	@echo "* build and execute notebooks:               make html-with-exec"
```

Then replace:

```
	@echo "* only serve:                                make serve"
```

with:

```
	@echo "* only serve:                                make serve"
	@echo "* serve and execute notebooks:               make serve-with-exec"
```

- [ ] **Step 12: Add the new targets to .PHONY in the Makefile**

Edit `docs/Makefile`. Replace:

```
.PHONY: help full-help html epub pdf linkcheck spelling spellcheck woke \
        vale pa11y run serve install pa11y-install   \
        vale-install pdf-prep pdf-prep-force clean clean-doc \
        update lint-md
```

with:

```
.PHONY: help full-help html html-with-exec epub pdf linkcheck spelling spellcheck woke \
        vale pa11y run serve serve-with-exec install pa11y-install   \
        vale-install pdf-prep pdf-prep-force clean clean-doc \
        update lint-md
```

- [ ] **Step 13: Install the bash kernel during venv setup**

Edit `docs/Makefile`. Replace:

```
	. $(DOCS_VENV); pip install $(PIPOPTS) --require-virtualenv \
	    --upgrade -r requirements.txt \
            --log $(DOCS_VENVDIR)/pip_install.log
	@test ! -f $(DOCS_VENVDIR)/pip_list.txt || \
```

with:

```
	. $(DOCS_VENV); pip install $(PIPOPTS) --require-virtualenv \
	    --upgrade -r requirements.txt \
            --log $(DOCS_VENVDIR)/pip_install.log
	. $(DOCS_VENV); python -m bash_kernel.install --sys-prefix
	@test ! -f $(DOCS_VENVDIR)/pip_list.txt || \
```

- [ ] **Step 14: Disable execution in the default run/html targets**

Edit `docs/Makefile`. Replace:

```
run: install
	. $(DOCS_VENV); $(DOCS_VENVDIR)/bin/sphinx-autobuild -b dirhtml --host $(SPHINX_HOST) --port $(SPHINX_PORT) "$(DOCS_SOURCEDIR)" "$(DOCS_BUILDDIR)" $(SPHINX_OPTS) $(SPHINX_AUTOBUILD_OPTS)
```

with:

```
run: install
	. $(DOCS_VENV); $(DOCS_VENVDIR)/bin/sphinx-autobuild -b dirhtml --host $(SPHINX_HOST) --port $(SPHINX_PORT) "$(DOCS_SOURCEDIR)" "$(DOCS_BUILDDIR)" $(SPHINX_OPTS) $(SPHINX_AUTOBUILD_OPTS) -D nb_execution_mode=off
```

Then replace:

```
# Does not depend on $(DOCS_BUILDDIR) to rebuild properly at every run.
html: install
	. $(DOCS_VENV); $(SPHINX_BUILD) --fail-on-warning --keep-going -b dirhtml "$(DOCS_SOURCEDIR)" "$(DOCS_BUILDDIR)" -w $(DEV_DIR)/warnings.txt $(SPHINX_OPTS)
```

with:

```
# Does not depend on $(DOCS_BUILDDIR) to rebuild properly at every run.
html: install
	. $(DOCS_VENV); $(SPHINX_BUILD) --fail-on-warning --keep-going -b dirhtml "$(DOCS_SOURCEDIR)" "$(DOCS_BUILDDIR)" -w $(DEV_DIR)/warnings.txt $(SPHINX_OPTS) -D nb_execution_mode=off
```

- [ ] **Step 15: Add the html-with-exec and serve-with-exec targets**

Edit `docs/Makefile`. Replace:

```
serve: html
	cd "$(DOCS_BUILDDIR)"; python3 -m http.server --bind $(SPHINX_HOST) $(SPHINX_PORT)
```

with:

```
serve: html
	cd "$(DOCS_BUILDDIR)"; python3 -m http.server --bind $(SPHINX_HOST) $(SPHINX_PORT)

html-with-exec: install
	. $(DOCS_VENV); $(SPHINX_BUILD) --fail-on-warning --keep-going -b dirhtml "$(DOCS_SOURCEDIR)" "$(DOCS_BUILDDIR)" -w $(DEV_DIR)/warnings.txt $(SPHINX_OPTS)

serve-with-exec: html-with-exec
	cd "$(DOCS_BUILDDIR)"; python3 -m http.server --bind $(SPHINX_HOST) $(SPHINX_PORT)
```

- [ ] **Step 16: Add jupyter cache cleanup to the clean target**

Edit `docs/Makefile`. Replace:

```
clean: clean-doc
	@test ! -e "$(DOCS_VENVDIR)" -o -d "$(DOCS_VENVDIR)" -a "$(abspath $(DOCS_VENVDIR))" != "$(DOCS_VENVDIR)"
	rm -rf $(DOCS_VENVDIR)
	rm -rf $(DEV_DIR)/node_modules/
	rm -rf $(DEV_DIR)/styles
	rm -rf $(VALE_CONFIG)
```

with:

```
clean: clean-doc
	@test ! -e "$(DOCS_VENVDIR)" -o -d "$(DOCS_VENVDIR)" -a "$(abspath $(DOCS_VENVDIR))" != "$(DOCS_VENVDIR)"
	rm -rf $(DOCS_VENVDIR)
	rm -rf $(DEV_DIR)/node_modules/
	rm -rf $(DEV_DIR)/styles
	rm -rf $(VALE_CONFIG)
	rm -rf .jupyter_cache
	rm -rf jupyter_execute
```

- [ ] **Step 17: Stage and verify the Makefile**

```bash
git add docs/Makefile
grep -nE 'html-with-exec|serve-with-exec|bash_kernel.install|nb_execution_mode=off|jupyter_execute' docs/Makefile
```
Expected: matches for both new targets, the bash_kernel install line, `nb_execution_mode=off` on `run` and `html`, and the jupyter cleanup lines. Also confirm there is exactly one `run: install` line (main's clean version replaces the branch's malformed duplicate):

Run: `grep -c '^run: install' docs/Makefile`
Expected: `1`.

- [ ] **Step 18: Re-add the notebook dependencies to requirements.txt**

`requirements.txt` auto-merged to main's version, silently dropping `myst-nb` and `bash_kernel`. Edit `docs/requirements.txt`. Replace:

```
sphinx-sitemap==2.9.0

# Vale dependencies
```

with:

```
sphinx-sitemap==2.9.0
myst-nb==1.1.2

# Vale dependencies
```

Then replace:

```
# Additional extensions 
sphinxcontrib-mermaid==2.0.0
```

with:

```
# Additional extensions 
sphinxcontrib-mermaid==2.0.0
bash_kernel==0.10.0
```

- [ ] **Step 19: Stage and verify requirements.txt**

```bash
git add docs/requirements.txt
grep -nE '^myst-nb==1.1.2$|^bash_kernel==0.10.0$|^canonical-sphinx==0.6.0$' docs/requirements.txt
```
Expected: all three lines present (`myst-nb==1.1.2`, `bash_kernel==0.10.0`, and main's `canonical-sphinx==0.6.0`).

- [ ] **Step 20: Confirm all conflicts are resolved**

Run: `git diff --name-only --diff-filter=U`
Expected: empty output (no unresolved conflicts). Also confirm no conflict markers remain:

Run: `grep -rnE '^(<<<<<<<|=======|>>>>>>>)' docs/ || echo "no markers"`
Expected: `no markers`.

- [ ] **Step 21: Complete the merge commit**

```bash
git commit --no-edit
```
(If the environment requires an explicit message, use: `git commit -m "Merge branch 'main' into fix/polish-tutorial.ipynb"`.)

Verify: `git log --oneline -1` shows a merge commit, and `git status --short` is clean (ignoring untracked build artifacts like `docs/.jupyter_cache/`, `docs/jupyter_execute/`).

---

### Task 3: Post-merge verification

Confirm the merged tree is internally consistent: the notebook feature is intact, `tutorial.md` is gone, no stray workflow targets `tutorial.md`, and the unit tests still pass.

**Files:**
- Verify only (no edits expected). If a check fails, fix within this task and amend or add a follow-up commit.

**Interfaces:**
- Consumes: the merge commit from Task 2 and the tests from Task 1.
- Produces: a validated branch ready for review/PR.

- [ ] **Step 1: Verify tutorial source-of-truth state**

```bash
test -f docs/tutorial.ipynb && echo "ipynb present"
test ! -f docs/tutorial.md && echo "md absent"
test -f docs/_extensions/fetch_tutorial_notebook.py && echo "extension present"
```
Expected: `ipynb present`, `md absent`, `extension present`.

- [ ] **Step 2: Verify no workflow references tutorial.md**

The branch removed `spread_docs.yaml` (which targeted `tutorial.md`); the merge preserves that deletion.

```bash
test ! -f .github/workflows/spread_docs.yaml && echo "spread_docs removed"
grep -rn "tutorial.md" .github/workflows/ || echo "no workflow references tutorial.md"
```
Expected: `spread_docs removed` and `no workflow references tutorial.md`.

- [ ] **Step 3: Verify the execute workflow still executes the notebook**

```bash
grep -n "make html-with-exec" .github/workflows/execute_tutorial_notebook.yaml
```
Expected: one match (the build step runs `make html-with-exec`, not `make html`).

- [ ] **Step 4: Verify the directory layout is main's (no .sphinx)**

```bash
test ! -d docs/.sphinx && echo "no .sphinx dir"
test -d docs/_static && test -d docs/_templates && test -d docs/_dev && echo "new layout present"
```
Expected: `no .sphinx dir` and `new layout present`.

- [ ] **Step 5: Re-run the unit tests**

Run: `tox -e unit -- tests/unit/test_fetch_tutorial_notebook.py -v`
Expected: 5 passed. (Fallback: `python -m pytest tests/unit/test_fetch_tutorial_notebook.py -v`.)

- [ ] **Step 6: Best-effort local non-RTD build sanity check**

The full docs toolchain may not be installed locally. If `make` docs deps are available, confirm the off-RTD path builds without executing the notebook (no cluster needed). Otherwise, skip and note it.

Run: `cd docs && make html 2>&1 | tail -20; cd ..`
Expected (if toolchain present): build completes; the fetch extension returns early because `READTHEDOCS` is unset; notebook is not executed. If dependencies are missing, note "local docs build skipped — covered by CI" and move on. Do not commit build artifacts (`docs/_build/`, `docs/.jupyter_cache/`, `docs/jupyter_execute/`).

- [ ] **Step 7: Final state confirmation**

Run: `git status --short`
Expected: clean tree apart from untracked build artifacts. Those artifacts are already ignored via `docs/.gitignore`; confirm they are not staged.

---

## Self-Review notes

- **Spec coverage:** Section 1 conflicts → Task 2 Steps 3–19; `tutorial.md` drop → Task 2 Step 3 + Task 3 Step 1; silent `requirements.txt` drop → Task 2 Steps 18–19; `.sphinx` relocation adopted via `--theirs` on conf.py/Makefile → Task 3 Step 4; Section 2 env-var tests → Task 1; Section 3 wiring/sequencing/verification → Tasks 1–3. All success criteria map to Task 3 checks.
- **Extra safeguard beyond the spec:** Task 3 Steps 2–3 guard two silent traps discovered during planning — the preserved `spread_docs.yaml` deletion and the `execute_tutorial_notebook.yaml` build step staying on `make html-with-exec`.
- **Type/name consistency:** Test references (`_fetch_notebook`, `setup`, `nb_execution_mode`, cache kwargs `path/uri/check_validity/overwrite`) match the module's actual signatures. Makefile edits consistently use main's variable names (`DOCS_VENV`, `DEV_DIR`, `SPHINX_BUILD`, `SPHINX_OPTS`, `DOCS_SOURCEDIR`, `DOCS_BUILDDIR`, `SPHINX_HOST`, `SPHINX_PORT`).
