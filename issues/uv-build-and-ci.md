---
status: unshaped
kind: build
appetite: big
---

# Build, lock, test and publish with uv

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

cmdkit builds with Poetry: metadata in `[tool.poetry]` (`pyproject.toml`), the `poetry-core`
backend, and `poetry.lock`. Everything around the build has aged:

- **Publish.** `.github/workflows/publish.yml` runs `JRubics/poetry-publish@v1.17` on
  `actions/checkout@v3` when a GitHub release is created, with the `PYPI_TOKEN` secret.
- **Tests.** `.github/workflows/tests.yml` runs on `actions/checkout@v2` and `actions/setup-python@v2`,
  installs with pip, and covers 3.10–3.13 only. The floor (`requires-python >=3.9`) and 3.14 are
  outside the matrix, though the suite passes on both.
- **Docs.** `.readthedocs.yaml` installs Poetry and runs `poetry install --with docs` on Python 3.10.
- **Dependencies.** Nothing configures dependabot, so its PRs target the default branch (`master`),
  not `develop`. Three are open, each bumping one transitive docs dependency in `poetry.lock`:
  #25 (idna 3.10 → 3.15), #27 (tornado 6.4.2 → 6.5.7) and #28 (soupsieve 2.6 → 2.8.4).
- **Classifiers** stop at 3.13.

## Why it was deferred

Adoption adds only the harness files. This is the first cycle after it.

## Outcome / vision

uv throughout, and nothing of Poetry left:

- PEP 621 `[project]` metadata; PEP 735 dependency groups for `dev` and `docs`; the extras `toml`
  (`tomli`, `tomli-w`) and `yaml` (`pyyaml`) unchanged in name, contents and lower bounds; no
  required runtime dependency.
- uv's build backend (`uv_build`) and a committed `uv.lock`. `poetry.lock` and `[tool.poetry]` go.
- CI: current major versions of the Actions, uv installed with `astral-sh/setup-uv`, the suite on
  3.9–3.14 on the same triggers as today (pushes to `master` and `develop`, PRs into `develop`).
- Publish: `uv build` and `uv publish` on release creation, with the existing `PYPI_TOKEN` secret.
  Moving PyPI to a trusted publisher is a settings change and out of scope.
- Read the Docs builds through uv.
- `.github/dependabot.yml` covers the `uv` and `github-actions` ecosystems, with
  `target-branch: develop`.
- Classifiers through 3.14.

The new lock supersedes #25, #27 and #28.

## Sketch of the acceptance criteria

- **R1** — WHEN `uv build` runs at the repository root, it SHALL produce an sdist and a wheel whose
  metadata match 2.7.7's: the name, `Requires-Python: >=3.9`, the `toml` and `yaml` extras with their
  packages, no unconditional `Requires-Dist`, and the `py.typed` marker in the wheel.
- **R2** — `uv lock --check` SHALL pass, and wherever idna, tornado or soupsieve appear in `uv.lock`
  they SHALL be at or above 3.15, 6.5.7 and 2.8.4.
- **R3** — The tests workflow SHALL run the whole suite on every Python from 3.9 to 3.14 on Linux,
  and on 3.9 and 3.14 on macOS and Windows.
- **R4** — WHEN a GitHub release is created, the publish workflow SHALL build with `uv build` and
  upload with `uv publish`, authenticated by `PYPI_TOKEN`.
- **R5** — Read the Docs SHALL build the documentation with uv.
- **R6** — Dependabot SHALL open PRs for `uv` and `github-actions` against `develop`.
- **R7** — The release recipe and `verify` in `AGENTS.md` § Factory SHALL describe the new build in
  the same commit (`version.source` becomes `project.version`, `bump.lock` becomes `uv lock`).

**Test that shows it:** diff the `METADATA` of the wheel `uv build` makes against the 2.7.7 wheel from
PyPI (only the version and classifiers differ); `uv lock --check`; a green `tests` run listing 3.9 and
3.14; `uv run --group docs sphinx-build docs docs/_build/html` exits 0.

## Notes

- `README.rst` says cmdkit "is tested for Windows, macOS, and Linux", and CI runs on Ubuntu only.
  Decided at adoption: the matrix gains macOS and Windows on the floor and the newest Python (R3),
  so the claim becomes true (`issues/docs-accuracy.md` holds the other stale claims).
- `__version__` is read from the installed metadata (`src/cmdkit/__init__.py:30`), so it needs no change.
- Files: `pyproject.toml`, `uv.lock`, `poetry.lock` (removed), `.github/`, `.readthedocs.yaml`,
  `AGENTS.md`. Of the later cycles, only `docs-accuracy` and the release candidate share files with it.
- Related: #25, #27, #28.
- Found by: adoption, 2026-11-10.
