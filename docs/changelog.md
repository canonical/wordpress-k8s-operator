(changelog)=

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Each revision is versioned by the date of the revision.

## 2026-05-19

- docs: Migrated the documentation URL under the Canonical domain.

- docs(charmkeeper): Upgraded documentation infrastructure from sphinx-docs-starter-pack 1.4.1 to sphinx-stack 2.0.
  - Renamed `.sphinx/` directory to `_dev/`.
  - Moved virtual environment from `.sphinx/venv/` to `.venv/`.
  - Moved `_static/` and `_templates/` to docs root.
  - Updated Makefile with new variable naming conventions.
  - Added `sphinx-rerediraffe` extension for redirects.
  - Bumped dependencies: `canonical-sphinx` 0.5.2 → 0.6.0, `sphinx-tabs` 3.4.7 → 3.5.0,
    `packaging` 25.0 → 26.2, `sphinxcontrib-svg2pdfconverter` 2.0.0 → 2.1.0.

## 2026-04-20

- docs: Updated landing pages to include more descriptions and organization.

## 2026-01-14

- docs: Added a GitHub workflow and Spread materials for automated testing of the tutorial.

## 2025-12-17

- docs: Moved architecture documentation from Explanation to Reference category.

## 2025-12-16

- chore: eject deprecated resource-centre theme

## 2025-12-11

- docs: Update to version 1.3.1 of the Canonical starter pack.

## 2025-11-19

- docs: Update requirements section of the tutorial based on UX research.

## 2025-11-10

- Refactor use consolidated workflows for RTD validation.

## 2025-11-04

- docs: Update the CONTRIBUTING.md file for the WordPress charm located in the canonical/wordpress-k8s-operator repository.
  Added the following sections to ensure consistency of style: Code of conduct, Submission, Describing pull requests, Signing commits.
- docs: Update URL and slug configuration parameters for the RTD project.

## 2025-10-28

- Refactor to fix some linting issues.

## 2025-09-26

- docs: Set up Read the Docs project to migrate the documentation.

## 2025-09-16

- docs: Update tutorial based on user feedback.

## 2025-07-02

- docs: Update README and tutorial based on user feedback.

## 2025-05-29

- docs: Fix issues found with local audit for style guide checks.

## 2025-03-11

- fix: use supported YoastSEO plugin version.
- docs: fix charm architecture diagram (separate charm containers boundary)

## 2025-03-10

- Add charm architecture diagram.
- Add changelog for tracking user-relevant changes.
