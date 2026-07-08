# Merge main and restore the Jupyter notebook tutorial

**Date:** 2026-07-08
**Branch:** `fix/polish-tutorial.ipynb`

## Problem

The branch `fix/polish-tutorial.ipynb` polishes the Jupyter notebook tutorial
feature (originally introduced by PR #366): it contains `docs/tutorial.ipynb`,
an enhanced `docs/_extensions/fetch_tutorial_notebook.py`, the
`execute_tutorial_notebook` / `publish_tutorial_notebook` workflows, and
notebook build targets in `docs/Makefile`.

Meanwhile, `main` advanced with PR #369 ("docs: upgrade RTD project and migrate
URL"), a large Read the Docs restructure that, as a side effect, **removed the
notebook feature**. #369 deleted `docs/_extensions/fetch_tutorial_notebook.py`,
restored `docs/tutorial.md`, rewrote `docs/conf.py`, `docs/Makefile`,
`docs/requirements.txt`, and moved `docs/.sphinx/` to `docs/_static/`,
`docs/_templates/`, and `docs/_dev/`.

Merging `main` into this branch therefore removes the notebook build
infrastructure the branch depends on and reintroduces `tutorial.md`. This work
re-integrates the notebook feature on top of the new RTD structure, then adds
tests to validate it.

## Goals

1. Merge `origin/main` into `fix/polish-tutorial.ipynb`, resolving all
   conflicts.
2. Keep the **notebook (`docs/tutorial.ipynb`) as the single source of truth**
   for the tutorial; drop the reintroduced `docs/tutorial.md`.
3. Restore notebook infrastructure removed or silently dropped by the merge,
   retargeted to main's new RTD directory layout.
4. Add local unit tests for the Read the Docs env-var code path in
   `fetch_tutorial_notebook.py`.

## Non-goals

- Notebook execution against a live Juju/MicroK8s cluster. The existing CI
  workflows (`execute_tutorial_notebook.yaml`, `publish_tutorial_notebook.yaml`)
  own end-to-end execution.
- Unrelated RTD refactors introduced by #369 — these are accepted as-is.
- Any charm code changes.

## Section 1 — Merge conflict resolution

A trial merge (`git merge --no-commit --no-ff origin/main`) produced four
git-flagged conflicts plus silent changes that must be handled manually.

### Git-flagged conflicts

1. **`docs/conf.py`** (content) — merge the notebook configuration into main's
   rewritten RTD `conf.py`. Notebook-specific pieces to preserve:
   - `sys.path.insert(0, os.path.abspath("_extensions"))`
   - `"fetch_tutorial_notebook"` in the `extensions` list
   - `nb_execution_mode = "cache"`, `nb_execution_timeout = 3600`,
     `nb_execution_show_tb = True`, `nb_execution_raise_on_error = True`
   - `exclude_patterns` entries: `"jupyter_execute"`, `".jupyter_cache"`
   - the `setup(app)` myst_nb compatibility shim (makes
     `myst_parser.sphinx_ext.main.setup_sphinx` a no-op, then
     `app.setup_extension("myst_nb")`)
2. **`docs/Makefile`** (content) — merge the notebook targets into main's
   rewritten Makefile: `html-with-exec`, `serve-with-exec`,
   `python -m bash_kernel.install --sys-prefix`, and jupyter cache cleanup
   (`rm -rf .jupyter_cache`, `rm -rf jupyter_execute`).
3. **`docs/_extensions/fetch_tutorial_notebook.py`** (modify/delete) — **keep
   the HEAD (branch) version**; main deleted it.
4. **`docs/tutorial.md`** (delete/modify) — **keep deleted**; the notebook is
   the source of truth.

### Silent drops / structural shifts (not git-flagged)

- **`docs/requirements.txt`** auto-merged cleanly but silently dropped
  `myst-nb==1.1.2` and `bash_kernel==0.10.0` (main removed them and git took
  that side). Re-add both. Otherwise adopt main's version bumps
  (e.g. `canonical-sphinx==0.6.0`, `sphinx-rerediraffe==0.0.3`).
- **`.sphinx/` relocation.** Main moved static/template assets to `_static/` and
  `_templates/` and dev tooling to `_dev/`. The branch's `conf.py` still
  references `.sphinx/_static`, a local `cookie-banner.css`, and a local
  `bundle.js` that main deleted. Retarget `html_static_path`, `templates_path`,
  `html_css_files`, and `html_js_files` to match main's new layout.
- **Toctree.** `docs/index.md` is identical on both sides and references the
  tutorial extensionless (`Tutorial <tutorial>`), so with `tutorial.md` removed
  it resolves to `tutorial.ipynb` automatically. No toctree edit required;
  verify this after the merge.

## Section 2 — Local test for the RTD env-var code path

CI covers notebook execution; local unit tests cover the extension's env-var
logic without a live cluster. The extension function `_fetch_notebook(app)`
branches on `os.environ["READTHEDOCS"]` and has graceful-degradation fallbacks.

**Location:** `tests/unit/test_fetch_tutorial_notebook.py` (fits the existing
`tests/unit/` structure).

**Approach:** Call `_fetch_notebook(app)` with a fake `app` object (a stub or
`unittest.mock.Mock` exposing `.srcdir`, `.config`, `.connect`) and monkeypatch
`urllib.request.urlopen` and `jupyter_cache.get_cache`. The module imports
`jupyter_cache` lazily inside the function, so the test mocks at the
`urllib` / `jupyter_cache` boundary and, if the dependency is not importable in
the unit-test environment, injects a fake `jupyter_cache` module into
`sys.modules`. The module is loaded by adding `docs/_extensions` to `sys.path`
(or via `importlib`).

**Code paths to cover:**

1. **Not on RTD** (`READTHEDOCS` unset): returns early; no download attempted;
   `nb_execution_mode` untouched.
2. **On RTD, download succeeds, cache succeeds:** `urlopen` called with the
   release download URL; `cache.cache_notebook_file` called with the expected
   arguments; temp file cleaned up afterwards.
3. **On RTD, download fails** (`URLError` / `OSError`): warning path; sets
   `app.config.nb_execution_mode = "off"`; no cache call.
4. **On RTD, caching fails** (`get_cache` or `cache_notebook_file` raises): sets
   `app.config.nb_execution_mode = "off"`; temp file still cleaned up.
5. **`setup(app)`:** registers the `builder-inited` hook and returns the
   parallel-safe metadata dict.

**Tooling:** pytest with `monkeypatch`, consistent with the repo.

## Section 3 — Test wiring, sequencing, and deliverables

### Test wiring

Placing the test under `tests/unit/` makes it run under the existing
`tox -e unit` command — no new CI needed. Because the test mocks at the
`urllib` / `jupyter_cache` boundary, it needs no real docs dependencies
installed. Coverage is scoped to the charm `src_path` and the extension lives in
`docs/_extensions/`, so this test does not affect the existing `fail_under = 90`
coverage gate; it is pure pass/fail validation.

### Execution sequence

1. `git merge origin/main` and resolve the four conflicts plus the silent drops
   (Section 1).
2. Restore/retarget `conf.py` paths (`.sphinx/` to `_static` / `_templates`),
   Makefile targets, and `requirements.txt` dependencies.
3. Write the unit tests (Section 2); run `tox -e unit` until all pass.
4. Best-effort local sanity check of the non-RTD build path (extension returns
   early; confirm no import/build errors), acknowledging the full docs stack may
   not be installed locally.
5. Verify `git status` is clean, notebook and all infra are present, and
   `tutorial.md` is gone.
6. Commit the merge.

### Deliverables

- A resolved merge commit on `fix/polish-tutorial.ipynb` with the notebook
  feature intact on the new RTD base.
- `tests/unit/test_fetch_tutorial_notebook.py` covering the five code paths.
- All notebook infrastructure retargeted to main's new directory layout.

## Success criteria

- `git status` clean after the merge; no conflict markers remain.
- `docs/tutorial.ipynb`, `docs/_extensions/fetch_tutorial_notebook.py`, and the
  two notebook workflows are present; `docs/tutorial.md` is absent.
- `docs/requirements.txt` contains `myst-nb` and `bash_kernel`.
- `docs/conf.py` references the new `_static` / `_templates` layout and retains
  the notebook config (`fetch_tutorial_notebook` extension, `nb_*` settings,
  myst_nb shim).
- `tox -e unit` passes, including the new tests.
