---
slug: uv-build-and-ci
title: Build, lock, test and publish with uv
kind: build
appetite: big
status: in_progress
branch: feature/uv-build-and-ci
base: develop
current_phase: P4
last_updated: '2026-11-10'
phases:
- id: P1
  name: Package with uv (PEP 621 metadata, uv_build, uv.lock)
  status: done
  satisfies:
  - R1
  - R2
  - R3
  - R4
  - R9
  - R10
  depends_on: []
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/uv-build-and-ci/verify/gate.sh P1
- id: P2
  name: Publish with uv build and uv publish
  status: done
  satisfies:
  - R3
  - R6
  depends_on:
  - P1
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/uv-build-and-ci/verify/gate.sh P2
- id: P3
  name: Read the Docs through uv, and dependabot
  status: done
  satisfies:
  - R3
  - R4
  - R7
  - R8
  depends_on:
  - P1
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/uv-build-and-ci/verify/gate.sh P3
- id: P4
  name: Tests workflow on uv across the matrix, with AGENTS.md
  status: in_progress
  satisfies:
  - R5
  - R9
  depends_on:
  - P1
  - P2
  - P3
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/uv-build-and-ci/verify/gate.sh P4
- id: P5
  name: Platform remediation, every job green, deferral ledger
  status: pending
  satisfies:
  - R5
  - R10
  - R11
  depends_on:
  - P4
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/uv-build-and-ci/verify/gate.sh P5
review:
  last_reviewed_commit: ''
  verdict: none
  blocked_reason: ''
  cycle: 0
---

# TECH.md — Build, lock, test and publish with uv

The **context engine and finite-state machine** for building this feature. The YAML
frontmatter above is the resume ground-truth (read it from the cycle worktree with the factory's
`next_phase.py`); the per-phase checklists below are the work. The build step executes the next
actionable phase, runs its `verify:` command, updates state with the factory's `set_phase.py`,
and makes one atomic code+state commit.

- **Vision / requirements (locked):** [`GOAL.md`](GOAL.md) — R-IDs are the contract.
- **Authoritative design:** [`PLAN.md`](PLAN.md).
- **Backing research:** [`research/00-digest.md`](research/00-digest.md) + briefs.

## Frontmatter field reference

- `status` (top): `planned | in_progress | blocked | in_review | done` (`done` is stamped by
  the publish step after confirmation, just before landing — the terminal state of the retained record)
- `appetite`: `small | big` — caps phase count and build-iteration budget (circuit breaker).
- `branch`, `base`: the cycle's branch (prefix per GOAL `kind`, from the profile's `branches`) and the
  profile's `base`.
- phase `status`: `pending | in_progress | done | blocked`
- `satisfies`: GOAL R-IDs this phase delivers (traceability anchor for the review step).
  **Artifact-deliverable R-IDs.** Some requirements are met by a *committed document* — a research
  audit, a protocol doc, an assessment — not by CLI-observable behaviour. Attach such an R-ID to the
  phase that produces and commits the artifact, and give that phase a content `verify:`
  (`test -f …`, a `grep -q` for the sections that must exist) rather than forcing a CLI drive.
  **Say so in the phase body**, because it changes who can grade it: the review step blinds its reviewer
  to all of `spec/`, so an R-ID whose evidence lives there is graded by the *orchestrator*, not the
  blind reviewer. Naming it in `TECH.md` is what lets the review skill route it correctly instead of
  reporting an unverifiable requirement.
- `depends_on`: phase ids that must be `done` first (a phase is actionable only when met).
- `parallel`: `true` only for genuinely independent, non-coupled work (docs, tests, isolated leaf
  modules). Any phase touching the profile's `coupled core` is always `false`.
- `hammerable`: `false` marks a correctness/security phase that scope-hammering must **never** cut.
- `hill`: `uphill` (still figuring it out) → `crest` (unknowns resolved) → `downhill` (just
  executing). A phase stuck `uphill` across builds is a raised hand → escalate to the human.
- `attempts`: durable failed-verify counter (absent = 0), bumped by `set_phase.py --phase P<n>
  --record-attempt` on every red verify gate; `next_phase.py` warns at ≥3 — the circuit breaker
  runs on this file, not on session memory.
- `verify`: the exact command that proves the phase (prefer driving the real CLI, not just tests —
  wrap CLI drives in the profile's `throwaway environment` helper, `<helper> sh -c "…"`, so they hit
  a disposable instance, never the developer's real data). A gate carrying `$( )` or quoting the
  calling shell would mangle is set with `set_phase.py --verify-file PATH`, not `--verify`.
- `review.cycle`: completed review passes, auto-incremented by every `set_phase.py --verdict …`;
  REVIEW.md's "Cycle {n}" mirrors it and the ≤3-cycle bound is graded against it. `--verdict approved`
  also clears `review.blocked_reason` unless one is passed explicitly.

## Conventions (apply to every phase)

- Commit conventions, code style, and load-bearing invariants come from the repo's `AGENTS.md` — it
  is the constitution. Walk the sections of its § Invariants that this change touches; that is the
  curated footgun checklist.
- One phase per build-step invocation by default; one atomic commit containing **both** the code and
  the `TECH.md` state change. The branch commit subject is the build step's (the profile's
  `branch commits`), not restated here; branch commits are squashed away at publish per the
  profile's `landing`. Trailers follow the profile's `branch commits`.
- The last phase carries the standing last-phase items: the deferral ledger, and every item the
  previous cycle's last phase carried for a project-level obligation (none: this is the repo's
  first cycle). A plan that drops one says why in `PLAN.md`.
- A PR body (when the profile's `landing` opens one) ends with an attribution naming the actual
  harness, model, and variant.
- A CLI/feature change obeys the profile's `same-commit rules` (§ Conventions in `AGENTS.md`): the
  help text, docs, or generated files it names change **in the same commit**.

### Cycle-specific

- **The gate.** Every phase's `verify:` is `sh spec/uv-build-and-ci/verify/gate.sh <mode>` (modes and
  their checks are in the script's header and `PLAN.md` § 6). The gate reads committed state, so stage
  and commit before trusting it: run it before the commit as a sanity pass,
  and again after the commit as the verdict. `verify/` is frozen at the plan commit, and the gate
  refuses to run when it differs; a remediation checker goes in
  `spec/uv-build-and-ci/remediation/`.
- **How to run it.** From `$WT`, with the sandbox off (the suite writes `/tmp/cmdkit/config`, sphinx
  extensions write user caches, `gh` reads its credentials, and the sandbox's proxy truncates
  Python's downloads of the reference wheel), with `UV_CACHE_DIR` and `UV_TOOL_DIR` set to
  per-step directories outside the repository. Tee the output to a log outside `$WT`.
- **External waits split P4 and P5** into Run A and Run B. Run A ends at the operator's outward
  steps; the builder never pushes, opens a PR, or writes to GitHub.
- **Re-grading CI after P5.** Any later commit that changes a file outside `spec/` (a review fix)
  invalidates `ci/P5.json`: the operator pushes it, waits for the PR's run, and runs
  `gate.sh evidence` at the new head before the review grades R5 or R11 and again before landing.
  At publish, `ledger.py --pr-body` checks that the PR body names every seed.
- **Phase bodies are instructions, not reports.** Results go in the build report and the commit
  body, never in a phase body: the ledger reads phase bodies for deferral phrases.
- No step adds a GitHub Action other than `actions/checkout` and `astral-sh/setup-uv`.

---

## Phase P1 — Package with uv (PEP 621 metadata, uv_build, uv.lock)
**Satisfies:** R1, R2, R3 (the `pyproject.toml` and lockfile half), R4, R9 (the release recipe and
the high-blast-radius list), R10 · **Depends on:** —
**Goal:** `uv build` makes the 2.7.7 package under the same version, from PEP 621 metadata and uv's
build backend, with a committed `uv.lock`; Poetry's table and lockfile are gone.

- [x] Rewrite `pyproject.toml` as `PLAN.md` § 2.1 gives it: `[project]` (name, version `2.7.7`,
      description, `readme`, `license = "Apache-2.0"`, `license-files = ["LICENSE"]`, one author
      table, keywords, classifiers with 3.14 added and the licence classifier kept,
      `requires-python = ">=3.9,<4.0"`, `dependencies = []`), `[project.optional-dependencies]`
      `toml` and `yaml` with 2.7.7's exact bounds, `[project.urls]` Homepage, Documentation and
      Repository, `[dependency-groups]` `dev` and `docs` translated from the Poetry carets,
      `[build-system]` `uv_build>=0.13.7,<0.14.0`. Keep `[tool.pytest.ini_options]` byte for byte.
- [x] `git rm poetry.lock`; `uv lock`; commit `uv.lock`.
- [x] `AGENTS.md` § Factory release recipe (same commit as the version's new home, per its own
      comment): `version.source: pyproject.toml project.version`, `bump.lock: uv lock`,
      `bump.files: [pyproject.toml, uv.lock]`, `diff_rule` naming cmdkit's entry in `uv.lock`; no
      Poetry left in the recipe. § Invariants high-blast-radius list names `uv.lock` and keeps
      `poetry.lock` (the list only widens).
- [x] Nothing under `src/` changes.
- **Verify:** `sh spec/uv-build-and-ci/verify/gate.sh P1`: `build_config.py package src`,
  `wheel_surface.py` (three wheels and the sdist's PKG-INFO against the pinned 2.7.7 wheel, then
  the install check), `workflow_config.py recipe`, and the profile's `verify` on an export.
- **Touches:** `pyproject.toml`, `poetry.lock` (removed), `uv.lock` (new), `AGENTS.md`.

## Phase P2 — Publish with uv build and uv publish
**Satisfies:** R6, R3 (`.github/` half, for the publish workflow) · **Depends on:** P1
**Goal:** creating a GitHub release builds with `uv build` and uploads with `uv publish`,
authenticated by `PYPI_TOKEN`, on current Actions.

- [x] Rewrite `.github/workflows/publish.yml` as `PLAN.md` § 2.2 gives it: trigger unchanged
      (`release: types: [created]`), `permissions: contents: read`, one `ubuntu-latest` job:
      `actions/checkout` at its current major, `astral-sh/setup-uv` at a full version tag of its
      current major (it publishes no floating major tag), `run: uv build`, `run: uv publish` with
      `env: UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}`. No other step, input or environment.
- [x] Re-read the current majors at build time (`git ls-remote --tags`); the gate reads them live.
- **Verify:** `sh spec/uv-build-and-ci/verify/gate.sh P2`: `workflow_config.py publish publishrun`
  (static checks, actionlint, and the workflow's own run lines on an export with the upload as a
  dry run).
- **Touches:** `.github/workflows/publish.yml`.

## Phase P3 — Read the Docs through uv, and dependabot
**Satisfies:** R7, R8, R3 (`.readthedocs.yaml`, and no Poetry left anywhere R3 names), R4 (the lock
after the docs group changes) · **Depends on:** P1
**Goal:** Read the Docs installs the docs group and cmdkit with uv; R7's command builds; dependabot
watches uv and Actions against `develop`.

- [x] `.readthedocs.yaml`: `build.os: ubuntu-24.04`, `build.tools.python: "3.13"`, and
      `python.install: [{method: uv, command: sync, groups: [docs]}]`; `sphinx.configuration`
      unchanged; no `build.jobs`.
- [x] Add `"setuptools<82"` to the `docs` group with a comment naming why
      (`sphinxcontrib-details-directive` imports `pkg_resources`; an exact uv environment has no
      setuptools), then `uv lock`. This is the one addition the lock needs for R7 (`PLAN.md` § 3).
- [x] `.github/dependabot.yml`: `version: 2`; `uv` and `github-actions` at `directory: "/"`,
      `target-branch: "develop"`, weekly.
- **Verify:** `sh spec/uv-build-and-ci/verify/gate.sh P3`: `workflow_config.py rtd dependabot`
  (schema-checked), `build_config.py package nopoetry`, `docs_build.py` (R7's command on an export,
  then Read the Docs' uv install emulated on the Python `.readthedocs.yaml` names).
- **Touches:** `.readthedocs.yaml`, `.github/dependabot.yml` (new), `pyproject.toml`, `uv.lock`.

## Phase P4 — Tests workflow on uv across the matrix, with AGENTS.md
**Satisfies:** R5 (the workflow, its triggers and jobs, the Linux jobs green), R9 (the rest) ·
**Depends on:** P1, P2, P3
**Goal:** the `tests` workflow runs the whole suite on the ten jobs with uv-installed Python and
locked dependencies, and `AGENTS.md` § Factory and § Invariants 4 describe it. Two runs.

Run A:
- [x] Rewrite `.github/workflows/tests.yml` as `PLAN.md` § 2.4 gives it: triggers unchanged; one
      job named `${{ matrix.os }} / py${{ matrix.python }}`, `runs-on: ${{ matrix.os }}`,
      `fail-fast: false`, matrix `os: [ubuntu-latest]` × `python: 3.9 … 3.14` plus `include` for
      macOS and Windows on 3.9 and 3.14; `env: UV_PYTHON_PREFERENCE: only-managed`; steps
      `actions/checkout`, `astral-sh/setup-uv` with `python-version: ${{ matrix.python }}`, and
      `run: uv run --locked python -m pytest -v`.
- [x] `AGENTS.md` (same commit, § Conventions): the profile's `verify` row says it installs the
      tree through uv's build backend (the command is unchanged); the release recipe's `gate` keeps
      3.9–3.14, the Linux matrix; § Invariants 4 drops the line recording CI's 3.10–3.13 coverage.
- [x] Commit (phase stays `in_progress`), then `sh spec/uv-build-and-ci/verify/gate.sh P4pre`
      green on the commit.
- [ ] Hand back to the operator with the commit SHA for its outward steps: push
      `feature/uv-build-and-ci` to `origin`, open a **draft** PR into `develop` (the cycle's PR;
      the `tests` workflow runs on PRs into `develop` only), then hold the wait on the PR's
      `tests` run.

Run B (after the run completes):
- [ ] `git fetch origin feature/uv-build-and-ci` so the remote-tracking ref is the pushed SHA.
- [ ] `sh spec/uv-build-and-ci/verify/gate.sh P4`: P4pre again, then `ci_evidence.py --require
      linux --expect-count <collected>`, which writes `spec/uv-build-and-ci/ci/P4.json` (every
      job's conclusion, Python and pytest summary). macOS and Windows outcomes are recorded here,
      not judged, and graded in P5.
- [ ] Commit `ci/P4.json` with the state change.
- R5's evidence is a GitHub run; the orchestrator grades it from `ci/P4.json` and `ci/P5.json`
  (under `spec/`, which the blind reviewer does not see).
- **Touches:** `.github/workflows/tests.yml`, `AGENTS.md`, `spec/uv-build-and-ci/ci/P4.json`.

## Phase P5 — Platform remediation, every job green, deferral ledger
**Satisfies:** R11, R5 (every job passes on the cycle's PR), R10 (whole-cycle) · **Depends on:** P4
**Goal:** every one of the ten jobs passes on the cycle's PR; any pre-existing macOS or Windows
failure is fixed in the tests or traced to a new seed, exactly as R11 allows.

Run A:
- [ ] Read `ci/P4.json`. For each failed macOS or Windows job, find the cause in its log
      (`gh run view --job <id> --log`, read only) and confirm it predates the cycle (the same tests
      on `origin/develop`'s code, not this cycle's build changes). Then, per R11:
      - a small fix confined to `tests/` that does not branch on the platform (a platform
        branch is not a fix, and the ledger refuses one): make it, and list it for the PR body; or
      - otherwise mark only the affected tests
        `@pytest.mark.xfail(sys.platform == '<darwin|win32>', reason='… issues/<slug>.md', strict=True)`,
        and write that seed now as `issues/<slug>.md` (from the issue template,
        `status: unshaped`) with its `ROADMAP.md` entry (`**Seed:** issues/<slug>.md`). The
        seed names each failing test by node id (`tests/<file>.py::<Class>::<test>`) and the base
        commit the failure was confirmed on.
      A failure caused by this cycle's changes is a bug to fix in the build files, not an R11 case.
      Nothing under `src/` changes either way; the matrix keeps every job.
- [ ] Deferral ledger: walk every earlier phase body here for deferral phrases and confirm each has
      its `issues/` file and ROADMAP entry (`ledger.py` checks the same mechanically).
- [ ] Commit, then `sh spec/uv-build-and-ci/verify/gate.sh P5pre` green on the commit.
- [ ] If anything outside `spec/` changed since P4's evidence SHA, hand back for the operator's push
      and wait (Run B follows). If nothing did (P4's run was already all green), there is nothing to
      push: run `gate.sh P5` now against P4's SHA and close the phase in this run.

Run B (after the run completes, when there was a push):
- [ ] `git fetch origin feature/uv-build-and-ci`; `sh spec/uv-build-and-ci/verify/gate.sh P5`
      (every phase's checks, `ledger.py --seeds`, `ci_evidence.py --require all`, which writes
      `ci/P5.json`). Commit `ci/P5.json` with the state change.
- [ ] Put `ledger.py --seeds`' two lists (seeds; changed test files) in the phase report: the PR
      body names each seed and each small fix (R11); publish writes the body and checks it with
      `ledger.py --pr-body`.
- **Verify:** `sh spec/uv-build-and-ci/verify/gate.sh P5` (`P5phase` runs only the ledger and the
  all-jobs evidence, for a fail-once mutation).
- **Touches:** `tests/` (only if R11 needs it), `issues/<slug>.md` and `ROADMAP.md` (only for a
  seed), `spec/uv-build-and-ci/ci/P5.json`.

---

## How the build step drives this

1. `next_phase.py` prints the next actionable phase (statuses are authoritative; the
   `current_phase` pointer is reconciled against them).
2. Pre-flight: the cycle worktree is clean, on `branch`, and `base` is reachable.
3. Execute every `[ ]` in the phase (consult `PLAN.md` / `research/` for detail).
4. Run the phase's `verify:` command — never advance on a checkbox alone.
5. Amend this file freely if reality diverges (regenerate frontmatter with `set_phase.py`; note the
   amendment in the commit body). STOP and escalate only on a **`GOAL.md` contradiction**.
6. Mark the phase `done`, advance `current_phase`, `--touch`; one `[{category}]` commit; stop and report.
