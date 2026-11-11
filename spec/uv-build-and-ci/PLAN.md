# PLAN — Build, lock, test and publish with uv

> **Status:** Draft for review · **Last updated:** 2026-11-10
> **Authoritative technical design.** The *how*. Vision/contract is [`GOAL.md`](GOAL.md);
> the phased executable roadmap is [`TECH.md`](TECH.md). Backing detail is in
> [`research/`](research/). Every design element traces to a GOAL R-ID.

## 1. Summary

Replace Poetry with uv in five vertical slices: the package first (PEP 621 `[project]`, the
`uv_build` backend, `uv.lock`, gated by a field-by-field comparison with the 2.7.7 wheel from
PyPI), then the publish workflow, then Read the Docs and dependabot, then the `tests` workflow
with its `AGENTS.md` lockstep, and last the cross-platform CI evidence and any R11 remediation.
Nothing under `src/` changes. Every phase is gated by one dispatcher, `verify/gate.sh`, whose
checks read committed state and were dry-run on a prototype of each phase's tree. The two CI
phases run as two runs each, around a push and a draft PR that the operator makes.

## 2. Design

### 2.1 The package (`pyproject.toml`, `uv.lock`) — P1

`pyproject.toml` becomes (the prototype's file, dry-run green):

```toml
[project]
name = "cmdkit"
version = "2.7.7"
description = "A command-line utility toolkit for Python."
readme = "README.rst"
license = "Apache-2.0"
license-files = ["LICENSE"]
authors = [
    { name = "Geoffrey Lentner", email = "glentner@purdue.edu" },
]
keywords = ["command-line", "utility", "toolkit"]
classifiers = [ …2.7.7's list, with "Programming Language :: Python :: 3.14" added after 3.13… ]
requires-python = ">=3.9,<4.0"
dependencies = []

[project.optional-dependencies]
toml = ["tomli>=2.1.0,<3.0.0", "tomli-w>=1.1.0,<2.0.0"]
yaml = ["pyyaml>=6.0.1,<7.0.0"]

[project.urls]
Homepage = "https://cmdkit.readthedocs.io"
Documentation = "https://cmdkit.readthedocs.io"
Repository = "https://github.com/glentner/cmdkit"

[dependency-groups]
dev = [ the Poetry dev group, carets translated: tomli, tomli-w, pyyaml (as the extras),
        "pytest>=7.4.4,<8.0.0", "hypothesis>=6.92.6,<7.0.0", "sphinx-autobuild>=2021.3.14,<2022.0.0" ]
docs = [ the Poetry docs group, carets translated (sphinx >=7.2.6,<8 … docutils >=0.21.1,<0.22) ]

[build-system]
requires = ["uv_build>=0.13.7,<0.14.0"]
build-backend = "uv_build"

[tool.pytest.ini_options]   # unchanged, byte for byte
```

- The extras keep 2.7.7's exact bounds (C3); the dev group repeats the three runtime packages
  rather than including an extra, so no dev or docs dependency becomes an extra (R3, C1).
- `license` as an SPDX string plus `license-files` is the only uv_build form that ships the licence
  text in the wheel (digest 1). The licence classifier stays: uv_build only warns (digest 2).
- uv_build's default module discovery (`src/cmdkit`) packs the ten modules and `py.typed`; nothing
  under `[tool.uv.build-backend]` is needed.
- `poetry.lock` is removed and `uv.lock` committed. The lock forks by Python and every branch meets
  R4's floors without constraints (digest 4).
- `src/cmdkit/__init__.py` reads `__version__` from installed metadata, so the wheel's version is
  what `cmdkit.__version__` reports (R10).

`AGENTS.md`, same commit (the recipe's own comment says the source line moves with the version):
release recipe `version.source: pyproject.toml project.version`, `bump.lock: uv lock`
(`uv lock` rewrites cmdkit's own entry; a bumped version without it fails `uv lock --check`,
probed), `bump.files: [pyproject.toml, uv.lock]`, `diff_rule` naming that entry; the
high-blast-radius bullet reads "`pyproject.toml` and the lockfile: `uv.lock` (`poetry.lock` until
the move to uv)".

### 2.2 Publishing (`.github/workflows/publish.yml`) — P2

```yaml
name: publish
on:
  release:
    types: [created]
permissions:
  contents: read
jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - name: Install uv
        uses: astral-sh/setup-uv@v10.3.3
      - name: Build distributions
        run: uv build
      - name: Publish to PyPI
        run: uv publish
        env:
          UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}
```

The trigger is unchanged. A token in the environment makes `uv publish` skip trusted publishing,
so no `id-token` permission is needed; it uploads `dist/*`, where `uv build` writes (digest 11).
Version tags are re-read at build time (the gate reads them live).

### 2.3 Read the Docs and dependabot — P3

`.readthedocs.yaml`: `build.os: ubuntu-24.04`, `build.tools.python: "3.13"`,
`python.install: [{method: uv, command: sync, groups: [docs]}]`, `sphinx.configuration:
docs/conf.py`. `uv sync` installs cmdkit itself (editable), which `docs/conf.py` imports for its
version. The `docs` group gains `"setuptools<82"` with a comment saying why (digest 5), and the lock
is regenerated.

`.github/dependabot.yml`: `version: 2`; `uv` and `github-actions`, each `directory: "/"`,
`target-branch: "develop"`, `schedule.interval: weekly`.

### 2.4 Tests workflow and `AGENTS.md` — P4

```yaml
name: tests
on:
  push:
    branches: [ master, develop ]
  pull_request:
    branches: [ develop ]
permissions:
  contents: read
jobs:
  test:
    name: ${{ matrix.os }} / py${{ matrix.python }}
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ ubuntu-latest ]
        python: [ '3.9', '3.10', '3.11', '3.12', '3.13', '3.14' ]
        include:
          - { os: macos-latest, python: '3.9' }
          - { os: macos-latest, python: '3.14' }
          - { os: windows-latest, python: '3.9' }
          - { os: windows-latest, python: '3.14' }
    env:
      UV_PYTHON_PREFERENCE: only-managed
    steps:
      - uses: actions/checkout@v7
      - name: Install uv and Python ${{ matrix.python }}
        uses: astral-sh/setup-uv@v10.3.3
        with:
          python-version: ${{ matrix.python }}
      - name: Test with pytest
        run: uv run --locked python -m pytest -v
```

- `python-version` makes setup-uv set `UV_PYTHON`, and `only-managed` makes uv install its own
  CPython rather than pick up a runner's (R5: "installing Python and dependencies with uv").
- `uv run --locked` installs the default `dev` group from the lock and fails on a stale lock, so CI
  also enforces R4's `uv lock --check`.
- The job name makes each of the ten jobs addressable by name in the CI evidence.

`AGENTS.md`, same commit (§ Conventions: verify, matrix and gate change together): the `verify`
row's prose says it installs the tree through uv's build backend (its command is unchanged: the
floor and newest Python); the release recipe's `gate` already loops 3.9–3.14, the Linux matrix;
§ Invariants 4 drops "Known limitation (recorded, not fixed): CI covers 3.10–3.13 only".

### 2.5 CI evidence and R11 — P4 Run B, P5

A pushed feature branch starts no `tests` run (digest 10), so P4's Run A ends with the operator's
two outward steps: push `feature/uv-build-and-ci`, open a **draft** PR into `develop`. That PR is
the cycle's PR: publish later marks it ready instead of creating one. Run B reads the run with
`gh` (reads only) and records it in `spec/uv-build-and-ci/ci/P4.json`; Linux is graded there.

P5 grades all ten jobs. A macOS or Windows failure that predates the cycle is fixed in `tests/`
when small, or else marked `@pytest.mark.xfail(sys.platform == '<darwin|win32>', reason='…
issues/<slug>.md', strict=True)` on exactly the affected tests, with a new `issues/<slug>.md`
(`status: unshaped`, naming each failing test's node id and the base commit the failure was
confirmed on) and its `ROADMAP.md` entry, written in the same phase. A small fix may not branch on
the platform: a platform branch is the xfail route. The matrix never shrinks, no test file is
renamed or removed, and `src/` never changes. If P4's run was already all green, P5 changes nothing outside
`spec/` and grades P4's run; otherwise Run A pushes (the operator) and Run B grades the new run.

### Requirement → design map

| R-ID | Design element(s) that satisfy it | Phase · gate check |
|------|-----------------------------------|--------------------|
| R1 | § 2.1 metadata and src layout; one sdist and one py3-none-any wheel | P1 · `wheel_surface.py` (root build, direct wheel, wheel from the sdist file) |
| R2 | § 2.1; field-by-field comparison, permitted differences only | P1 · `wheel_surface.py` against the pinned 2.7.7 wheel |
| R3 | § 2.1 (no Poetry table, uv_build, groups), § 2.2–2.4 (no Poetry steps) | P1 · `build_config.py package`; P3, P5 · `build_config.py nopoetry` |
| R4 | § 2.1 `uv.lock`; § 2.3 relock | P1, P3 · `build_config.py package` (`uv lock --check`, floors) |
| R5 | § 2.4 workflow; § 2.5 evidence | P4 · `workflow_config.py tests`, `ci_command.py`, `ci_evidence.py --require linux`; P5 · `--require all` |
| R6 | § 2.2 | P2 · `workflow_config.py publish publishrun` |
| R7 | § 2.3 Read the Docs, `setuptools<82` | P3 · `docs_build.py`, `workflow_config.py rtd` |
| R8 | § 2.3 dependabot | P3 · `workflow_config.py dependabot` |
| R9 | § 2.1 recipe lines, § 2.4 verify, gate and § Invariants 4 | P1 · `workflow_config.py recipe`; P4 · `workflow_config.py agents` |
| R10 | no `src/` change; version from metadata | P1, P4, P5 · `build_config.py src`; P1 · `wheel_surface.py` install check |
| R11 | § 2.5 | P5 · `ledger.py` (xfail form, seed, ROADMAP), `ci_evidence.py --require all` |

## 3. Invariant gate (AGENTS.md constitution check)

Walked before research and again on the drafted design. Sections touched: the high-blast-radius
list, § 1, § 4, § Conventions. § 2 and § 3 are untouched: nothing under `src/` changes, and the
gate checks it.

- **High-blast-radius paths** — `pyproject.toml`, the lockfile and `publish.yml` all change, so
  research ran (trigger 2). The list gains `uv.lock` and keeps `poetry.lock` (it only widens).
- **§ 1 Compatibility** — consumers get the same package: R1/R2's comparison with the 2.7.7 wheel
  from PyPI is the gate, and `src/` is unchanged. The version and the 3.14 classifier are the only
  consumer-visible changes.
- **§ 4 Footprint** — the floor stays 3.9; CI now covers 3.9–3.14, matching the release gate, so the
  known-limitation line goes. No required runtime dependency (gated). Import effects unchanged.
- **§ Conventions** — the version lives only at the recipe's `version.source`, which moves with it
  (P1); verify, the matrix and the gate change together (P4); no R/P ids enter source, workflows or
  config (gate scripts live under `spec/`).
- **Profile** — every phase touches the coupled core's build files, so every phase is
  `parallel: false`.

### Deviation justifications

| Deviation | Why needed | Simpler alternative rejected because |
|-----------|-----------|--------------------------------------|
| R1/R2 read `Requires-Python` as a specifier set: uv_build writes `>=3.9, <4.0`, 2.7.7 `>=3.9,<4.0`. | uv_build normalises the separator; no input yields the unspaced form. Installers parse it, so the install surface is equal. R2 already compares requirements as parsed. | A byte comparison fails on encoding only, and no metadata change could pass it. |
| The description body is compared with trailing newlines stripped. | poetry-core's 2.7.7 body ends with one extra newline; the text is otherwise byte-equal to `README.rst`. | A byte comparison fails on the serializer, not the value. |
| `Author: Geoffrey Lentner` stays beside `Author-email: Geoffrey Lentner <glentner@purdue.edu>`. | uv_build writes both from one author table. `Author` keeps 2.7.7's exact value, so it is not a difference, and `Author-email` is exactly R2 item 3's combined value. The gate allows `Author` only absent or equal to 2.7.7's. | An email-only author table drops the name from `Author-email`, which then fails item 3. |
| The licence classifier is kept; R2 item 5 does not apply. | uv_build builds with it (a warning) and PyPI accepts it (digest 2), so the item's condition is not met. The gate requires it. | Dropping it would fail R2 as worded. |
| `setuptools<82` joins the `docs` group. | R7: an exact uv environment has no setuptools, and a docs extension imports `pkg_resources` (gone in 82). Without it R7's command exits 2 (planner's mutant D06). | Dropping the extension changes the docs' rendering and `docs/conf.py`, outside this cycle. |
| `astral-sh/setup-uv` is pinned to `v10.3.3`, not `@v10`. | It publishes no floating major tag since v8, so `@v10` cannot resolve. "Current major" is read as a published tag of the newest major (the gate checks both, live). | `@v10` fails every run; an older major with a floating tag fails R5/R6. |
| `UV_PYTHON_PREFERENCE: only-managed` in the tests job. | R5 says Python is installed with uv; without it uv may use a Python the runner image already has. | Leaving it out makes which interpreter runs depend on the runner image. |
| CI evidence comes from a **draft PR opened during build** (P4 Run A), not at publish. | The `tests` workflow runs only on PRs into `develop` and pushes to `develop`/`master` (R5 fixes the triggers), and R11's remediation must land before review. | Adding a feature-branch trigger changes R5's triggers; waiting for publish puts R11's test changes after the blind review. |
| R9's `AGENTS.md` edits land in two phases: the recipe lines with `pyproject.toml` (P1), the `verify` prose, `gate` and § Invariants 4 with `tests.yml` (P4). | The recipe's own comment ties `version.source` to the version's move; § Conventions ties verify, matrix and gate to `tests.yml`. Each lockstep holds within its commit, and the landing squashes them into one. | One phase for both would hold `version.source` stale for a commit or move the matrix before CI exists. |
| R11's small-fix branch may not branch on the platform; an xfail's seed must name the failing test and the base commit. | R11 says "fix it in the tests alone WHERE that fix is small": a test that returns early on one platform passes CI without fixing anything (adversarial review H3). Naming the test and the commit records that the failure predates the cycle. | Trusting the builder's judgment leaves a fake fix green in every gate. |
| `TECH.md`'s template prose names the factory's steps generically ("the build step", "the factory's `next_phase.py`") and drops the template's example of another project's last-phase item. | The repository is public; the template's tool paths and project names are internal. The standing last-phase items are unchanged: the deferral ledger, and no project-level item (this is the first cycle). | Copying the template verbatim publishes internal paths. |
| The high-blast-radius list keeps `poetry.lock` ("until the move to uv"). | § Invariants: the list only widens. R3 covers `pyproject.toml`, `.github/` and `.readthedocs.yaml`; this line describes the repository and configures no build. | Removing it breaks the list's own rule. |

Each row was read against R1, R2, R3, R5, R6, R9 and R10 as worded; none bends an R-ID, and none
needs the GOAL changed.

## 4. Rabbit holes (resolved)

- **Can uv_build reproduce 2.7.7's surface, licence and all?** Yes, with the SPDX string plus
  `license-files`; the table forms ship no licence file and cannot combine with `license-files`.
  The prototype's wheels pass the full R1/R2 gate ([`01`](research/01-pypi-licence-and-publish.md),
  [`00-digest.md`](research/00-digest.md) 1–3).
- **Would PyPI refuse the licence classifier beside `License-Expression`?** No: only `License`
  beside `License-Expression` is rejected ([`01`](research/01-pypi-licence-and-publish.md) § 1).
- **Can the lock meet R4's floors on 3.9?** Yes; soupsieve 2.8.4 is the newest that supports 3.9
  and is exactly the floor ([`03`](research/03-docs-and-dependabot.md) § 3).
- **Does Read the Docs build through uv?** Natively (`method: uv`), once `setuptools<82` covers a
  `pkg_resources` import ([`03`](research/03-docs-and-dependabot.md) § 1).
- **Does Python 3.9 still install under uv on all three platforms, and does pytest 7.4 run on
  3.14?** Yes to both ([`02`](research/02-ci-matrix.md) §§ 2, 4).
- **Will macOS and Windows pass?** macOS passes locally; Windows is predicted to pass. R11 is a
  contingency, not a planned change ([`02`](research/02-ci-matrix.md) § 3).
- **How is CI proven without GitHub writes by the builder?** A draft PR the operator opens, and
  `gh` reads checked against a real run's JSON and log shapes ([`02`](research/02-ci-matrix.md) § 5).
- **Adversarial design review.** One reviewer ran; see § 7 for what it found and changed.

## 5. Risks & open questions

- **Outward steps mid-build.** P4 Run A needs the operator to push the branch and open a draft PR
  into `develop`; P5 may need a second push. Publish then marks the existing PR ready rather than
  creating it, writes the seeds and small fixes `ledger.py --seeds` lists into its body, and checks
  it with `ledger.py --pr-body` (R11).
- **Evidence after P5.** A review fix that changes anything outside `spec/` needs a push, the PR's
  run, and `gate.sh evidence` at the new head before R5 and R11 are graded or the cycle lands.
- **A platform-branching fix is refused.** If a genuinely small Windows or macOS fix needs a
  platform branch in a test, the ledger refuses it and the xfail route applies; a builder that
  disagrees raises it rather than editing the frozen gate.
- **Publish is proven statically.** No release is cut in this cycle, so `publish.yml`'s first live
  run is the 2.8.0 release. The gate runs its own run lines on an export with `uv publish
  --dry-run`. The release-candidate cycle owns the first live publish.
- **Read the Docs is emulated.** It builds `latest` from the default branch, so the live build
  follows the release. The gate runs R7's command and an emulation of Read the Docs' uv install on
  the Python the config names.
- **Dependabot takes effect on the default branch** and its security updates ignore
  `target-branch` (they go to `master`). R8 is met as configuration; the behaviour starts at the
  release.
- **Action versions move.** The gate reads the newest major live; a new major between plan and build
  turns the gate red, and the builder updates the pin.
- **Runner images move** (`ubuntu-latest` is migrating to 26.04). The suite is image-agnostic;
  `only-managed` keeps the interpreter uv's own.
- **The gate needs the network and the sandbox off.** The sandbox's proxy truncated Python's
  download of the reference wheel (curl was unaffected); run gates unsandboxed, per TECH § Conventions.
- **R11 changes need care.** A Windows or macOS failure caused by this cycle's build changes is a
  bug, not an R11 case; P5 confirms "predates" by running the same tests against
  `origin/develop`'s code before choosing a remedy.

## 6. Verification strategy

One dispatcher, `verify/gate.sh <mode>` (POSIX sh), runs the checks in order and stops at the first
red. Every check reads committed state (`git archive` or `git show` at HEAD; the profile verify runs on
an export) and runs Python isolated (`uv run --isolated --no-project --python 3.14 … python -I`). Footprint: strictly
sequential, no background processes, peak about 1 GB (sphinx).

| Script | Checks |
|---|---|
| `wheel_surface.py` | builds at the root (sdist, then wheel from it), a wheel straight from the tree, and a wheel from the sdist file; compares each wheel's METADATA, and the sdist's PKG-INFO, field by field with the 2.7.7 wheel, fetched by pinned URL and sha256, under R2's permitted differences and R1's literal surface; files under `cmdkit/` exactly the ten modules and `py.typed`, byte-equal to `src/`; `dist-info` holds only METADATA, WHEEL, RECORD and the licence; then installs the wheel in an isolated environment and checks `cmdkit.__version__`. |
| `build_config.py` | `package`: Poetry table and lockfile gone, uv_build, `[project]`, groups `dev`/`docs` equal to the base's Poetry groups with carets translated (docs may add `setuptools<82` alone; no `[tool.uv] dev-dependencies`), extras exactly `toml`/`yaml`, `uv lock --check`, floors on every locked version. `nopoetry`: no Poetry in `pyproject.toml`, `.github/`, `.readthedocs.yaml`. `src`: no change under `src/` since the merge-base with `origin/develop`, and no `.gitattributes` change. |
| `workflow_config.py` | `publish`, `publishrun`, `tests`, `rtd`, `dependabot`, `recipe`, `agents`: each workflow against its exact shape (top-level and job keys, steps in order, step keys, no inputs or environment beyond the design's, no soft failures, no other actions or secrets), Actions at the live current major, actionlint, the JSON schemas for Read the Docs and dependabot, and `AGENTS.md`'s recipe, verify, gate, lists and § Invariants 4. |
| `docs_build.py` | R7's command verbatim on an export; Read the Docs' uv install emulated on the configured Python. |
| `ci_command.py` | `ci`: `tests.yml`'s own run line on an export, on uv-managed 3.9 and 3.14. `profile`: the profile's `verify` on an export. `collect`: tests collected at HEAD, never fewer than at the base (75). |
| `ci_evidence.py` (+ `_selftest.py`) | the PR's `tests` run on the pushed SHA: ten named jobs; each graded job concluded success, its log shows pytest on the right platform and Python, and its summary shows only passed and (off Linux, where a decorator targets that platform) xfailed tests, exactly the collected count; Linux or all graded, the rest recorded. The self-test runs 26 fixture cases. |
| `ledger.py` | TECH deferrals name seeds; every added xfail is a strict single-platform decorator naming a new, unshaped, ROADMAP-indexed seed that names the failing test and the base commit; no added line branches on the platform; nothing else hides a test (skips, `__test__`, collection hooks, renames, removals, pytest options). `--pr-body` (publish) checks the PR body names each seed. |

Modes: `P1`, `P2`, `P3`, `P4pre` (pre-push), `P4`, `P5pre` (pre-push, every phase's checks plus
the ledger), `P5`, `P5phase` (P5's own checks only, for build's fail-once mutation), `evidence`
(the R5/R11 re-grade at a later head, writing nothing). Every mode first refuses to run if
`verify/` has uncommitted changes or differs from the plan commit's copy.

**Dry runs on the prototype** (a detached worktree at `origin/develop`; a plan commit carrying
`spec/` with the final `verify/`, then one commit per phase; uv 0.13.7, warm caches, sandbox off):

| Gate | Tree | Result | Time |
|---|---|---|---|
| `P1` | P1 | green; profile verify 75 passed on 3.9 and 3.14 on an export | 3 s |
| `P2` | P2 | green | 1 s |
| `P3` | P3 | green; R7's command and the Read the Docs emulation (3.13) | 7 s |
| `P4pre` | P4 | green; CI command 75 passed on uv-managed 3.9 and 3.14; collected 75 at base and HEAD; self-test 26/26 | 7 s |
| `P5pre` | P5 (= P4: no R11 change, no seed) | green, every check together; `seeds: none` | 20 s |
| `P4`, `P5`, `P5phase`, `evidence` | — | stop cleanly at the first step that needs the pushed branch (`no origin/feature/uv-build-and-ci`); the `gh` plumbing was run against a real run of this repository's old workflow (correct reds) and is covered by the fixture self-test | — |
| freeze | P2 / P4 | an uncommitted edit to `verify/`, and a committed one after the plan commit, both refuse to run | — |
| full suite | P5 | 75 passed on each of 3.9–3.14, no skips | 8 s |

Planner mutants, all as expected: 34 against `wheel_surface.py` and `build_config.py` (33 red; a
version bump with `uv lock` green), 36 against `workflow_config.py` and `docs_build.py` (all red),
24 R11/ledger simulations on the P5 tree (2 allowed cases green, 22 red). The mutant drivers are
throwaway and stay out of the tree; build's own fail-once mutation follows the build step.

## 7. Adversarial design review

One fresh reviewer ran against the GOAL, this design and the drafted gates, attacking the prototype
through its own clone (31 tool calls). It found four HIGH, five MEDIUM and five LOW problems; each
is folded in, and its mutants are in the planner's suites above.

| Finding | What it showed | Fold |
|---|---|---|
| H1 · R6 | `publish.yml` passed with steps out of order, a workflow-level `defaults: working-directory`, setup-uv pinned to an old uv, and job `environment`/`container`/`timeout-minutes`. | Both workflows are checked against their exact shape: top-level and job keys, steps in order, step keys, no setup-uv inputs in publish. |
| H2 · R5, R11 | Renaming a test module or adding `__test__ = False` hid tests on every platform, so equal job counts stayed equal. | `ci_command.py collect` pins the collected count (never below the base's 75), and every graded job must run exactly that many; the ledger refuses `__test__`, collection hooks, and renames or removals under `tests/`. |
| H3 · R11 | An early `return` on win32 in every test passed as a "small fix". | No added test line may branch on the platform; seeds must name the failing test and the base commit. |
| H4 · R5, R11 | Evidence goes stale if a review fix changes code after P5. | `gate.sh evidence` re-grades at a later head; TECH § Conventions says when. |
| M1 · R5 | P4 went red over macOS/Windows jobs it only records. | `--require linux` records the others without judging them. |
| M2 · R11 | Nothing checked that the PR body names each seed. | `ledger.py --pr-body`, run at publish. |
| M3 · R3 | Dropping or loosening a group dependency passed. | Groups must equal the base's Poetry groups, carets translated; docs may add `setuptools<82` alone; no `[tool.uv] dev-dependencies`. |
| M4 | A report line in a phase body read as a deferral. | TECH: phase bodies are instructions, not reports. |
| M5 | `verify/` was frozen only on paper, and the profile verify ran on the working copy. | Every gate mode checks `verify/` against the plan commit and the index; the profile verify runs on an export. |
| L1 · R11 | `xfailed` on Linux passed. | Linux xfails fail; elsewhere only on a platform a decorator names. |
| L2 · R1, R10 | `git archive` honours `.gitattributes`. | A `.gitattributes` change in the cycle fails `build_config.py src`. |
| L3 · R1 | The sdist's PKG-INFO was never compared. | Compared field by field, with its licence files read from the sdist. |
| L4 | The TECH template's prose named internal tools and another project. | Reworded generically (deviation row). |
| L5 · R9 | § Invariants 4's check missed rewordings. | Bullets read whole across line breaks; any limitation bullet about CI fails, and the coverage rule must remain. |

The reviewer's two questions are answered in the design: "predates the cycle" is recorded in each
seed (test node id and base commit), and the operator re-runs the evidence after review fixes.

---

*Backing research: [`research/00-digest.md`](research/00-digest.md).*
