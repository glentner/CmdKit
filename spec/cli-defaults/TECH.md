---
slug: cli-defaults
title: Argument errors reach stderr, and a group can show its help when run bare
kind: fix
appetite: small
status: in_review
branch: fix/cli-defaults
base: develop
current_phase: done
last_updated: '2026-11-11'
phases:
- id: P1
  name: Argument errors reach stderr when no logging is configured
  status: done
  satisfies:
  - R1
  - R2
  - R3
  - R6
  - R7
  - R8
  - R9
  depends_on: []
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/cli-defaults/verify/gate.sh P1
- id: P2
  name: A group with ALLOW_NOARGS shows its help when run bare
  status: done
  satisfies:
  - R4
  - R5
  - R6
  - R8
  depends_on:
  - P1
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/cli-defaults/verify/gate.sh P2
review:
  last_reviewed_commit: ''
  verdict: none
  blocked_reason: ''
  cycle: 0
---

# TECH.md — Argument errors reach stderr, and a group can show its help when run bare

The **context engine and finite-state machine** for building this change. The YAML frontmatter
above is the resume ground truth; the per-phase checklists below are the work. The build step
executes the next actionable phase, runs its `verify:` command, updates the state, and makes one
atomic code+state commit.

- **Vision / requirements (locked):** [`GOAL.md`](GOAL.md) — R-IDs are the contract.
- **Authoritative design:** [`PLAN.md`](PLAN.md).
- **Backing research:** [`research/00-digest.md`](research/00-digest.md) and its briefs.

## Frontmatter field reference

- `status` (top): `planned | in_progress | blocked | in_review | done`.
- `appetite`: `small | big` — caps phase count and build-iteration budget (circuit breaker).
- `branch`, `base`: the cycle's branch (prefix per GOAL `kind`, from the profile's `branches`) and
  the profile's `base`.
- phase `status`: `pending | in_progress | done | blocked`
- `satisfies`: GOAL R-IDs this phase delivers (traceability anchor for the review).
- `depends_on`: phase ids that must be `done` first.
- `parallel`: `true` only for genuinely independent, non-coupled work. Any phase touching the
  profile's `coupled core` is always `false`.
- `hammerable`: `false` marks a correctness phase that scope-hammering must never cut.
- `hill`: `uphill` → `crest` → `downhill`. A phase stuck `uphill` across builds is a raised hand.
- `attempts`: durable failed-verify counter (absent = 0).
- `verify`: the exact command that proves the phase.
- `review.cycle`: completed review passes.

## Conventions (apply to every phase)

- Commit conventions, code style, and load-bearing invariants come from the repo's `AGENTS.md` — it
  is the constitution. Walk the sections of its § Invariants that this change touches; that is the
  curated footgun checklist.
- One phase per build-step invocation by default; one atomic commit containing **both** the code and
  the `TECH.md` state change. The branch commit subject is the build step's (the profile's
  `branch commits`), not restated here; branch commits are squashed away at publish per the
  profile's `landing`. Trailers follow the profile's `branch commits`.
- The last phase carries the standing last-phase items: the deferral ledger, and every item the
  previous cycle's last phase carried for a project-level obligation (none: the previous cycle's
  last-phase items were its own CI evidence and its ledger). A plan that drops one says why in
  `PLAN.md`.
- A PR body (when the profile's `landing` opens one) ends with an attribution naming the actual
  harness, model, and variant.
- A CLI/feature change obeys the profile's `same-commit rules` (§ Conventions in `AGENTS.md`): the
  help text, docs, or generated files it names change **in the same commit**.

### Cycle-specific

- **The gate.** Each phase's `verify:` is `sh spec/cli-defaults/verify/gate.sh P<n>`; its modes and
  checks are in the script's header and `PLAN.md` § 6. It installs and grades an export of the git
  index and diffs the index against the plan commit, so **stage the phase's work before running
  it**. `verify/` is frozen at the plan commit and the gate refuses to run when it differs; a
  remediation checker goes in `spec/cli-defaults/remediation/`.
- **How to run it.** From the cycle worktree, sandboxed or not. Set `UV_CACHE_DIR` and
  `UV_TOOL_DIR` to per-step directories outside the repository and keep `TMPDIR` writable (the
  export goes to a fresh directory there and is left in place). A sandboxed run names `pypi.org`
  and `files.pythonhosted.org` for uv. The gate never runs the full suite: the profile's `verify`
  does that before the push, and until the open tests-to-`tmp_path` change lands it needs `/tmp`
  writable.
- **A known flaky test.** The gate seeds Hypothesis; the profile's `verify` does not. A red
  `test_app_invalid_options` there with a prefix of a long option (`opt='he'`) is the pre-existing
  defect in `issues/test-invalid-options-help-prefix.md`, not this change: move `.hypothesis/`
  aside (Hypothesis replays a saved failure) and re-run.
- **Phase bodies are instructions, not reports.** Results go in the build report and the commit
  body, never in a phase body: the ledger reads phase bodies.

---

## Phase P1 — Argument errors reach stderr when no logging is configured
**Satisfies:** R1, R2, R3, R6, R7, R8, R9 · **Depends on:** —
**Goal:** with no logging configured and the default `log_critical`, `main` writes an argument
error's bare message to stderr, once, keeping its status; configured handlers and a replaced
`log_critical` see exactly what they see in 2.7.7; nothing is attached to any logger.

- [x] `src/cmdkit/app.py`: add `import sys` to the standard-libs group; add the private module
      function `_last_resort_would_print(logger, level)` as `PLAN.md` § 2 specifies (GOAL C6: the
      enabled check, the `logging.lastResort` presence and level check, then the walk along
      `propagate` that any handler stops whatever its level, except an exact
      `logging.NullHandler` on the `cmdkit` logger), with a docstring.
- [x] `Application.main`: in the `ArgumentError` branch, after `cls.log_critical(error)`, write
      `print(error, file=sys.stderr)` when `cls.log_critical == log.critical` and
      `_last_resort_would_print(log, logging.CRITICAL)` is true. Leave the other branches as they
      are.
- [x] `Application.main`'s docstring: how an argument error is reported.
- [x] `docs/api/app.rst`: the `log_critical` / `log_exception` paragraph describes the default
      report on stderr and that an override alone handles the message.
- [x] `AGENTS.md`: delete the last bullet of § Invariants 3, the one recording that `ArgumentError`
      messages are dropped with no logging configured, and change nothing else in the file.
- [x] `tests/test_app.py`: add the `no_logging_configured()` context manager (hides the root
      logger's handlers inside a test body and restores them in place) and the tests `PLAN.md`
      § 2 lists for R1, R2, R3, C6 and R7, side by side; existing tests stay byte for byte.
- [x] Stage the work, then run the verify.
- **Verify:** `sh spec/cli-defaults/verify/gate.sh P1`.
- **Touches:** `src/cmdkit/app.py`, `tests/test_app.py`, `docs/api/app.rst`, `AGENTS.md`.

## Phase P2 — A group with ALLOW_NOARGS shows its help when run bare
**Satisfies:** R4, R5, R6, R8 · **Depends on:** P1
**Goal:** an `ApplicationGroup` with `ALLOW_NOARGS = True` run with an empty command line prints
what its `--help` prints and returns `exit_status.success`; without the opt-in a bare group, and a
plain application either way, behave as in 2.7.7.

- [x] `src/cmdkit/app.py`: add `ApplicationGroup.main` as `PLAN.md` § 2 specifies (an empty
      command line becomes `['--help']` when `cls.ALLOW_NOARGS is True`, then the base `main`),
      with a docstring. `from_cmdline` stays as it is.
- [x] `docs/api/app.rst`: the `ALLOW_NOARGS` paragraph states `exit_status.usage` for a bare run
      and what the attribute does on a group; the `ApplicationGroup` section gains an
      `ALLOW_NOARGS` entry.
- [x] `tests/test_app.py`: the R4 tests (`main([])` and `main(None)` on an `ALLOW_NOARGS` group,
      byte-equal to its `--help` output, status 0) directly after `test_app_group_usage`, and
      `Group.main(None)` printing usage with status 1; the plain-application tests for
      `ALLOW_NOARGS` with and without a required positional.
- [x] Deferral ledger: walk P1 and this phase for any work set aside; each item has an `issues/`
      seed from the template and a `ROADMAP.md` entry, staged with this phase.
- [x] Stage the work, then run the verify.
- **Verify:** `sh spec/cli-defaults/verify/gate.sh P2`.
- **Touches:** `src/cmdkit/app.py`, `tests/test_app.py`, `docs/api/app.rst`.

---

## How the build step drives this

1. The next-phase helper prints the next actionable phase (statuses are authoritative; the
   `current_phase` pointer is reconciled against them).
2. Pre-flight: the cycle worktree is clean, on `branch`, and `base` is reachable.
3. Execute every `[ ]` in the phase (consult `PLAN.md` / `research/` for detail).
4. Run the phase's `verify:` command — never advance on a checkbox alone.
5. Amend this file freely if reality diverges (note the amendment in the commit body). STOP and
   escalate only on a **`GOAL.md` contradiction**.
6. Mark the phase `done`, advance `current_phase`; one `[fix]` commit; stop and report.
