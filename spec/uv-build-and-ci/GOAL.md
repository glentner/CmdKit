# GOAL — Build, lock, test and publish with uv

> **Origin spec.** The *what* and *why*: the locked contract the review grades against.
> The *how* lives in [`PLAN.md`](PLAN.md) and [`TECH.md`](TECH.md), written by the plan step.
> Edit requirements here; do **not** silently drift them during build.

- **slug:** uv-build-and-ci
- **kind:** build
- **appetite:** big

## Problem

cmdkit builds with Poetry: metadata under `[tool.poetry]` in `pyproject.toml`, the `poetry-core`
backend, and `poetry.lock`. Everything around the build has aged with it.

- **Publish.** `.github/workflows/publish.yml` runs a third-party Poetry publish action
  (`JRubics/poetry-publish@v1.17`) on `actions/checkout@v3` when a GitHub release is created,
  authenticated by the `PYPI_TOKEN` repository secret. A release is a PyPI publish, and a PyPI
  version can never be reused, so this path matters more than its size suggests.
- **Tests.** `.github/workflows/tests.yml` runs on `actions/checkout@v2` and
  `actions/setup-python@v2`, installs with pip, and covers Python 3.10–3.13 on Ubuntu only. The
  floor (`requires-python >=3.9`) and 3.14 sit outside the matrix, although the suite passes on
  both, and `README.rst` claims cmdkit "is tested for Windows, macOS, and Linux". `AGENTS.md`
  § Invariants 4 records the gap as a known limitation.
- **Docs.** `.readthedocs.yaml` pip-installs Poetry and runs `poetry install --with docs` on
  Python 3.10.
- **Dependencies.** Nothing configures dependabot, so its PRs target the default branch (`master`)
  rather than `develop`. Three are open, each bumping one transitive docs dependency in
  `poetry.lock`: #25 (idna 3.10 → 3.15), #27 (tornado 6.4.2 → 6.5.7), #28 (soupsieve 2.6 → 2.8.4).
- **Classifiers** stop at 3.13.

The contributor and release tooling the project already relies on (`AGENTS.md` § Factory: `verify`
and the release recipe's `gate`) runs through uv, while the project itself still builds and locks
through Poetry. Two tools describe one build, and the release recipe carries comments promising the
move.

This is the first cycle of 2.8.0, and 2.x is additive (`AGENTS.md` § Invariants 1): a consumer
installing the next release must get the same package, with the same extras, importing the same
way. Only the build around it changes.

## Outcome / vision

uv throughout, and nothing of Poetry left in the build:

- PEP 621 `[project]` metadata, uv's build backend, and a committed `uv.lock`. `[tool.poetry]` and
  `poetry.lock` are gone.
- The wheel and sdist a consumer receives are the 2.7.7 package under a new version: same name,
  same Python floor, same `toml` and `yaml` extras, no required runtime dependency, the `py.typed`
  marker, and the same importable modules.
- CI runs the whole suite on every Python from 3.9 to 3.14 on Linux, and on 3.9 and 3.14 on macOS
  and Windows, with current Actions, so the README's platform claim becomes true.
- A GitHub release publishes with `uv build` and `uv publish`, still authenticated by `PYPI_TOKEN`.
- Read the Docs builds through uv.
- Dependabot watches the `uv` and `github-actions` ecosystems and opens its PRs against `develop`.
- The repository's own build description in `AGENTS.md` § Factory matches the new build.

## Acceptance criteria (the contract)

- **R1** — WHEN `uv build` runs at the repository root, it SHALL produce one sdist and one
  `py3-none-any` wheel whose install surface matches the cmdkit 2.7.7 wheel on PyPI apart from the
  version: `Name: cmdkit`; `Requires-Python` admitting every Python from 3.9 and none below it;
  `Provides-Extra` exactly `toml` and `yaml`; `Requires-Dist` exactly `tomli` and `tomli-w` under
  `extra == "toml"` and `pyyaml` under `extra == "yaml"`, with the version ranges set by
  [NEEDS CLARIFICATION: C3], and no unconditional `Requires-Dist`; and the same files under
  `cmdkit/` (the ten modules and `py.typed`), with the license text in the wheel's metadata. A
  wheel built from that sdist SHALL meet the same criterion.
- **R2** — The built distribution's descriptive metadata SHALL carry 2.7.7's values: the summary,
  the keywords, the author and address, the Apache-2.0 licence, the documentation, home and
  repository URLs, and `README.rst` as the long description (`text/x-rst`). The classifiers SHALL
  list every Python minor version from 3.9 to 3.14. The permitted differences from 2.7.7's
  `METADATA` are set by [NEEDS CLARIFICATION: C4].
- **R3** — The repository SHALL hold no Poetry build configuration: no `poetry.lock`, no
  `[tool.poetry]` table, no Poetry build backend, and no Poetry step in `.github/` or
  `.readthedocs.yaml`. `pyproject.toml` SHALL declare uv's build backend, and the development and
  documentation dependencies SHALL live in the form set by [NEEDS CLARIFICATION: C1].
- **R4** — `uv.lock` SHALL be committed, and `uv lock --check` SHALL pass against `pyproject.toml`.
  WHERE idna, tornado or soupsieve appear in `uv.lock`, every locked version of them SHALL be at or
  above 3.15, 6.5.7 and 2.8.4 respectively.
- **R5** — The `tests` workflow SHALL run the whole suite on every Python minor version from 3.9 to
  3.14 on Linux, and on 3.9 and 3.14 on macOS and Windows, installing Python and dependencies with
  uv. It SHALL trigger on pushes to `develop` and `master` and on pull requests into `develop`, and
  every Action it uses SHALL be at its current major version. Every job SHALL pass on the cycle's
  PR, subject to [NEEDS CLARIFICATION: C2].
- **R6** — WHEN a GitHub release is created, the `publish` workflow SHALL build the distributions
  with `uv build` and upload them to PyPI with `uv publish`, authenticated by the existing
  `PYPI_TOKEN` repository secret, with every Action it uses at its current major version.
- **R7** — Read the Docs SHALL install the documentation dependencies and cmdkit through uv, and
  `uv run` of `sphinx-build` over `docs/` with the documentation dependencies SHALL exit 0 at the
  repository root.
- **R8** — `.github/dependabot.yml` SHALL configure the `uv` and `github-actions` ecosystems, each
  with `target-branch: develop`.
- **R9** — `AGENTS.md` § Factory SHALL describe the new build, changed together with
  `.github/workflows/tests.yml` (§ Conventions): `verify` runs under uv's build backend; the
  release recipe's `version.source` reads `project.version`, `bump.lock` runs `uv lock`, and
  `bump.files` lists `pyproject.toml` and `uv.lock`; the `gate` covers the same Python versions as
  the Linux matrix; and the high-blast-radius list names `uv.lock`. § Invariants 4 no longer
  records CI's 3.10–3.13 coverage as a known limitation.
- **R10** — The cycle SHALL change nothing under `src/cmdkit/`. `cmdkit.__version__` SHALL equal
  the version in `pyproject.toml` when cmdkit is installed from the built wheel.

**Test that shows it:** build at the root and compare the wheel's `METADATA` and file list with the
2.7.7 wheel from PyPI field by field (R1, R2); `uv lock --check` and a search of `uv.lock` for the
three packages (R4); a green `tests` run on the cycle's PR listing every job of R5; a reading of
`publish.yml` and `.github/dependabot.yml` (R6, R8); `uv run --group docs sphinx-build docs
docs/_build/html` (R7, in the form C1 settles); `git diff origin/develop -- src/` is empty, and the
import check in the release recipe's `gate` passes on the built wheel (R10).

## Non-goals (no-gos)

- Any change to runtime behaviour, the public interface, or anything under `src/cmdkit/`
  (§ Invariants 1). The version string and classifiers are the only consumer-visible changes.
- Moving PyPI publishing to a trusted publisher: that is a repository setting outside this cycle.
  The `PYPI_TOKEN` secret stays.
- Changing the Python floor, renaming an extra, or changing what an extra installs.
- Moving the suite off `/tmp/cmdkit/config`: that is `issues/tests-use-tmp-path.md`, a later cycle.
- Other stale documentation claims (the Python floor in the docs, docstring examples): that is
  `issues/docs-accuracy.md`, which waits on this cycle. `README.rst` needs no edit here: R5 makes its
  platform claim true.
- Upgrading the documentation toolchain (Sphinx, the theme, extensions) beyond what the lock needs
  to meet R4 and R7.
- Gating the publish workflow on the test workflow, signing or attesting distributions, or adding
  linters, type checkers or coverage to CI.
- Merging or closing dependabot PRs #25, #27 and #28: the lock supersedes them (R4); closing them is
  the maintainer's act on GitHub.
- Cutting a release. Version 2.8.0 is set by the release candidate cycle.

## Clarifications

Decided at the cycle's start (2026-11-10), carried as given:

- **Q:** Does Poetry stay alongside uv? — **A:** No. Poetry and `poetry.lock` go entirely: PEP 621
  `[project]` metadata, uv's build backend, `uv.lock`, and `uv build` and `uv publish` in the
  publish workflow (resolved 2026-11-10).
- **Q:** How does publishing authenticate? — **A:** With the existing `PYPI_TOKEN` repository
  secret; no trusted-publisher switch (resolved 2026-11-10).
- **Q:** The Python floor and the extras? — **A:** `requires-python >=3.9`, so 2.7.7's `<4.0` upper
  bound on Python is not carried over. The `toml` and `yaml` extras keep their names and contents.
  Nothing a consumer installs or imports changes apart from the version and classifiers, and the
  comparison with the 2.7.7 wheel is the test (resolved 2026-11-10).
- **Q:** The CI matrix and triggers? — **A:** The whole suite on 3.9–3.14 on Linux and on 3.9 and
  3.14 on macOS and Windows, with current Action versions; pushes to `develop` and `master`, PRs
  into `develop` (resolved 2026-11-10).
- **Q:** Read the Docs and dependabot? — **A:** Read the Docs builds through uv; a
  `.github/dependabot.yml` covers `uv` and `github-actions` and targets `develop` (resolved
  2026-11-10).
- **Q:** The open dependabot PRs? — **A:** The lock supersedes #25, #27 and #28: wherever idna,
  tornado and soupsieve appear in `uv.lock`, they are at or above those PRs' versions (resolved
  2026-11-10).
- **Q:** Does `AGENTS.md` change in this cycle? — **A:** Yes, in the same cycle: `verify`, the
  release recipe (`version.source` becomes `project.version`; `bump.lock` and `bump.files` gain
  `uv.lock`) and the `tests.yml` matrix move together (resolved 2026-11-10).
- **Q:** The suite's `/tmp/cmdkit/config`? — **A:** Stays until `issues/tests-use-tmp-path.md`;
  out of scope here (resolved 2026-11-10).

Open:

- **C1** — [NEEDS CLARIFICATION: Where do the `dev` and `docs` dependency sets live? (a) PEP 735
  `[dependency-groups]` named `dev` and `docs`, as the seed proposes: not published in the wheel's
  metadata, installed with `uv sync --group` / `uv run --group`; (b) uv's own `[tool.uv]`
  development dependencies plus a docs group; (c) other. They can't become extras: that would
  change what a consumer can install (R1).]
- **C2** — [NEEDS CLARIFICATION: R5 adds macOS and Windows jobs the suite has never run on. If a
  job there fails for a pre-existing reason, what does this cycle do? On Windows the suite's
  `/tmp/cmdkit/config` is created as `\tmp\cmdkit\config` on the working drive, and `_eval` tests
  run `echo` through `cmd.exe`, so it may pass unchanged, but nobody has run it. (a) Fix only the
  test side, minimally, and only where the fix is needed to pass; no `src/` change. (b) Record each
  failure as a new `issues/` seed and mark the affected tests as expected failures on that platform,
  naming the seed. (c) Drop the failing platform from the matrix and record a seed. (d) Stop the
  cycle for a human decision at the first such failure.]
- **C3** — [NEEDS CLARIFICATION: Do the extras keep 2.7.7's upper bounds? 2.7.7's wheel declares
  `tomli>=2.1.0,<3.0.0`, `tomli-w>=1.1.0,<2.0.0` and `pyyaml>=6.0.1,<7.0.0` (Poetry caret ranges).
  The cycle's decision says nothing a consumer installs may change, which reads as (a) keep the
  same ranges, both bounds; the seed said "unchanged in name, contents and lower bounds", which
  reads as (b) keep the lower bounds and drop the caps.]
- **C4** — [NEEDS CLARIFICATION: The literal `METADATA` diff against 2.7.7 cannot be limited to the
  version and classifiers. poetry-core 1.9.1 wrote `Metadata-Version: 2.1` with `Home-page:`,
  `Author:` / `Author-email:` and `License:` fields and parenthesised `Requires-Dist` ranges. PEP 621
  has no home-page or bare author-email field, so the home page becomes a `Project-URL` and the
  author an `Author-email: Name <address>`; an SPDX licence string becomes a `License-Expression`
  (PEP 639) under a newer `Metadata-Version`; range formatting differs by backend; and
  `Requires-Python` loses `<4.0` by the decision above. Is the test (a) field-by-field equivalence
  of values, with those encoding differences permitted and the license classifier allowed to go if
  the backend requires it, as R1 and R2 are written, or (b) something stricter?]

## Related materials

- Seed: `issues/uv-build-and-ci.md`; `ROADMAP.md` Part I, order 1.
- Superseded dependabot PRs: <https://github.com/glentner/cmdkit/pull/25>,
  <https://github.com/glentner/cmdkit/pull/27>, <https://github.com/glentner/cmdkit/pull/28>
  (all three open against `master`, 2026-11-10).
- The 2.7.7 baseline: <https://pypi.org/project/cmdkit/2.7.7/> (wheel
  `cmdkit-2.7.7-py3-none-any.whl`, built by poetry-core 1.9.1).
- Files: `pyproject.toml`, `poetry.lock` (removed), `uv.lock` (new), `.github/workflows/tests.yml`,
  `.github/workflows/publish.yml`, `.github/dependabot.yml` (new), `.readthedocs.yaml`, `AGENTS.md`
  § Factory and § Invariants.
- `src/cmdkit/__init__.py` reads `__version__` from the installed metadata, so it needs no change.
- Later cycles that share files: `issues/docs-accuracy.md`, `issues/release-candidate-2-8-0.md`;
  `issues/tests-use-tmp-path.md` owns the suite's `/tmp` path.
