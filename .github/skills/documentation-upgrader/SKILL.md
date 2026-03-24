# Skill: Sphinx Docs Starter Pack Upgrader

## 1. Skill Overview
**Name:** `sphinx_docs_starter_pack_upgrader`
**Description:** Automates the process of upgrading the upstream Sphinx documentation starter pack (`canonical/sphinx-docs-starter-pack`) for the `wordpress-k8s-operator` project. It ensures that upstream core tooling is updated while project-specific configurations, custom files, and strictly pinned Python dependencies are preserved.

## 2. Triggers / Invocation
**Intent/Keywords:**
* "Upgrade the docs starter pack"
* "Sync documentation with canonical/sphinx-docs-starter-pack"
* "Run the Sphinx docs update"
* "Bump the sphinx starter pack version"

## 3. Prerequisites and Environment
**Required Tools:** The agent must have execution access to `git`, `python3`, and `make`.
**Workspace Requirements:** The agent must execute this skill within a cloned workspace of the `wordpress-k8s-operator` repository. All pathing in the instructions assumes execution from the `docs/` directory.

## 4. Inputs / Parameters
* **`target_branch`** (Optional): The name of the Git branch to create for this upgrade. Default: `chore/update-docs-starter-pack`.
* **`commit_message`** (Optional): Custom commit message. Default: `chore(docs): bump sphinx-docs-starter-pack from <old_version> to <new_version>`.

---

## 5. System Prompt / Core Instructions

*When executing this skill, you MUST strictly follow the instructions defined below. Do not skip steps or ignore the strict dependency pinning rules.*

### 5.1 Objective and Scope
**Goal:** Your task is to upgrade the documentation starter pack files within the `wordpress-k8s-operator` repository to match the latest upstream release of `canonical/sphinx-docs-starter-pack`. 
**Boundaries:** You must successfully update the core Sphinx tooling and linting configurations while strictly preserving the project's custom documentation files, specific Makefile targets, and custom Python dependencies.

### 5.2 Project Context & Directory Structure
* **Documentation Root:** All documentation-related files and commands are located in the `docs/` directory. Unless specified otherwise, execute commands from within this directory.
* **Starter Pack Core:** The `docs/.sphinx/` directory contains the core starter pack files managed by the upstream project (e.g., HTML/CSS/JS assets, Vale linters, and metrics scripts).
* **Configuration Files:** Files like `docs/conf.py`, `docs/Makefile`, and `docs/requirements.txt` contain both upstream defaults and project-specific customizations. Exercise caution when modifying them.
* **Update Script:** The primary tool for fetching updates is `docs/.sphinx/update_sp.py`. This script compares local file hashes against the GitHub API to identify changed or new upstream files.

### 5.3 Pre-Upgrade Analysis
Before making any changes, gather context on the upgrade:
1. **Check Local Version:** Read the contents of `docs/.sphinx/version` to determine the currently installed version of the starter pack.
2. **Fetch Upstream Data:** Identify the latest release version of `canonical/sphinx-docs-starter-pack` via the GitHub API.
3. **Review Changelog:** Read the upstream `CHANGELOG.md` for the versions between the local version and the latest version. Take note of any breaking changes, deprecated features, or manual migration steps.

### 5.4 Step-by-Step Execution

#### Step 5.4.0: Create the Upgrade Branch
1. From the repository root, create and switch to the upgrade branch: `git checkout -b <target_branch>` using the `target_branch` parameter from Section 4.
2. All subsequent steps should be executed on this branch.

#### Step 5.4.1: Run the Update Script
1. Navigate to the `docs/` directory.
2. Execute the update script by running: `make update` (this triggers `python3 .sphinx/update_sp.py`).
3. **Analyze Output:** The script will download modified files into a temporary `docs/.sphinx/update/` directory. If entirely new files are introduced by the upstream release, it will generate a `docs/NEWFILES.txt` file listing them. It will also print missing Python dependencies to the console.

#### Step 5.4.2: Merge Updated Files
1. Systematically move and overwrite the files from the temporary `docs/.sphinx/update/` directory to their correct locations in `docs/.sphinx/`.
2. **Edge Case:** If the `docs/.sphinx/update_sp.py` script itself was downloaded into the update folder, overwrite the old script and **re-run `make update`** to ensure the new script logic fetches all necessary files.

#### Step 5.4.3: Handle New Files
1. Check for the existence of `docs/NEWFILES.txt`.
2. If it exists, read the file paths and ensure these new files are correctly moved from the update directory to the active `.sphinx/` directory and staged for version control tracking.

#### Step 5.4.4: Reconcile Dependencies (`requirements.txt`)
Update `docs/requirements.txt` with strict adherence to the following rules:
* **Strict Pinning:** Every dependency in `docs/requirements.txt` MUST be explicitly pinned to an exact version (e.g., `package==1.2.3`). Do not leave any dependencies unpinned, even if the upstream starter pack does.
* **Selective Upgrades:** The update script's package list is the complete upstream set, not a delta of what changed. Cross-reference it against the existing `docs/requirements.txt` and only act on packages that are genuinely absent or whose version constraint is strictly newer than what is already pinned.
* **Resolving Loose Constraints:** When the upstream specifies a loose constraint (e.g. `canonical-sphinx~=0.6`), query `https://pypi.org/pypi/<package>/json` to find the latest version satisfying that constraint and pin to it exactly (e.g. `canonical-sphinx==0.6.0`). Never copy a loose constraint verbatim into `requirements.txt`.
* **Preserve Custom Extensions:** Do not remove custom dependencies that are required by `wordpress-k8s-operator` but are absent in the upstream starter pack (e.g., `sphinxcontrib-mermaid`).
* **Limit Scope:** ONLY upgrade dependencies that were modified or introduced by the starter pack upgrade. Do NOT proactively upgrade other unrelated dependencies; a separate bot handles general dependency maintenance.

### 5.5 Validation and Testing
After applying all file and dependency updates, verify that the documentation builds and passes all checks. Execute the following commands from the `docs/` directory:

1. **Environment Setup:** Run `make clean` first to remove the existing virtual environment and build artefacts. This is required because `make install` is a no-op when the venv directory already exists, so without this step the updated `requirements.txt` would be silently ignored. Then run `make install` to rebuild the virtual environment from scratch.
2. **Build Documentation:** Run `make html`. The build must succeed without any Sphinx warnings or errors.
3. **Run Automated Linting Checks:**
    * Run `make spelling`
    * Run `make woke`
    * Run `make linkcheck`
    * Run `make vale`
4. **Fixing Failures:** Use the following triage rules depending on which check fails:
    * **`make spelling` / `make vale` (false positive):** If Vale or the spelling check flags a word that is correct per the Canonical style guide (a false positive), append it to `docs/.custom_wordlist.txt`.
    * **`make vale` (real content error):** If Vale flags a genuine content issue (e.g. a product name missing a required qualifier like `Ubuntu 20.04` → `Ubuntu 20.04 LTS`), fix the content directly. Do not add real errors to the wordlist.
    * **`make linkcheck` (broken link):** Run `git diff HEAD` on the affected file to determine whether the broken link predates this upgrade. If pre-existing, fix the URL to point to the correct current location. Only add a URL to `linkcheck_ignore` in `docs/conf.py` for links that are structurally correct but transiently unreachable (e.g. rate-limited). If the broken link was introduced by this upgrade, fix it before committing.

### 5.6 Cleanup and Finalization
1. **Clean Temporary Files:** Delete the temporary `docs/.sphinx/update/` directory and the `docs/NEWFILES.txt` file.
2. **Update Changelog:** Check for a changelog file at `docs/changelog.md` first; if it does not exist, fall back to `CHANGELOG.md` in the repository root. If neither exists, skip this step. Add a new entry modelled after the most recent existing entry for structure and date formatting. The entry should note the old and new starter pack versions, the dependency changes made to `requirements.txt`, and any content or linting fixes applied during the upgrade.
3. **Commit Changes:** Stage your changes and create a git commit using the target branch and commit message parameters.

---

## 6. Expected Output & Post-Conditions

### Success Criteria:
* A new Git branch is created successfully.
* Upstream files in `docs/.sphinx/` match the latest release, while custom files and configurations remain intact.
* `docs/requirements.txt` is updated with strictly pinned versions, preserving custom extensions like `sphinxcontrib-mermaid`.
* Documentation builds successfully without warnings via `make html`.
* All linters pass successfully.
* Changes are staged, committed, and ready for a Pull Request.

### Failure Handling:
* If `make html` fails or linter errors cannot be automatically resolved (e.g., via `docs/.custom_wordlist.txt`), the agent must:
  1. Abort the commit.
  2. Clean up the temporary workspace files.
  3. Report the specific build or linting error to the user for manual intervention.