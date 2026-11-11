# REVIEW — Tests write only to pytest's temporary directories

> Adversarial QA by `code-review`, run in an isolated/clean context (a subagent; where the runtime
> has none, `code-review`'s sequential fallback). The correctness pass grades the branch diff against
> [`GOAL.md`](GOAL.md) + the repo's `AGENTS.md` § Invariants **only** — it does not see
> `PLAN.md`/`TECH.md` (avoids grading-its-own-homework / plan-sycophancy). Every finding cites an
> **executed** command, not an assertion.

- **Reviewed commit:** a3cec2817a69871e3f5e33fbd25d2691edbd24f9  ·  **Base:** develop  ·  **Date:** 2026-11-10
- **Verdict:** approved
- **Cycle:** 1 of ≤3. Mirrors `review.cycle` in `TECH.md`.

A single fresh reviewer graded the change. It saw `GOAL.md`, the review rubric, `AGENTS.md`, the
runnable worktree, and the diff and log against `origin/develop` with `spec/` excluded. It wrote its
own probes and didn't see the plan's gate scripts. The pass paused once for a usage limit and resumed
in the same context, with no repeated work. `GOAL.md`'s commit after the shape commit, `c1acd1f`,
holds clarifications C1 and C2, ruled at the GOAL gate before planning.

## Verification run

- **The profile's `verify` with the sandbox on (`/tmp` denied):** 75 passed on Python 3.9.25
  (pytest 8.4.2) and 75 passed on Python 3.14.6 (pytest 9.2.0).
- **Sandbox check:** `os.open` and `os.mkdir` under `/tmp` both get EPERM.
- **Negative control:** under the same sandbox, the base suite stops at collection with
  `PermissionError: … '/tmp/cmdkit'`.
- **Write audit** (`sys.addaudithook`, installed before pytest is imported): one run per Python,
  each with a fresh `--basetemp`, sandboxed, plus one unsandboxed run on 3.14.
  - The tests write 28 files, all under the basetemp.
  - Outside the basetemp and the C1 caches, no write has a `tests/` frame on its stack. The 9 such
    events on 3.9 and 11 on 3.14 are all pytest's own: capture `TemporaryFile`s and `/dev/null`.
  - Control: the same detector finds a `tests/` frame on all 28 basetemp writes.
- **R2, unsandboxed:** `/tmp/cmdkit` absent beforehand. `--basetemp` at a fresh directory gives 75
  passed on each Python, and `/tmp/cmdkit` is absent afterwards.
- **R4, all from one checkout sharing one `TMPDIR`:**
  - Round 0 runs the literal `verify` command for each Python side by side.
  - Three audited rounds run with a start barrier.
  - One round runs four at once.
  - Every run passed 75. Each run's tests wrote 28 files and read back 24, all in its own
    `pytest-N`. Across every overlapping pair, no path one run read or wrote had been written by
    another.
- **R5:** 75 node IDs at `b9efaca` and at HEAD, identical. The base was collected sandboxed, with a
  shim for its import-time `makedirs`. Mapping `{tmp_path}` back shows the test bodies identical
  apart from the `Path` import and the removed module-level `/tmp` block.
  `grep -rnE "['\"]/tmp" tests/` prints nothing.
- **Orchestrator:**
  - `gate.sh P1` is green with the sandbox off: static, selftest, audit, concurrent, and R2 with
    `/tmp/cmdkit` absent.
  - `gate.sh tmpdenied` is green with the sandbox on.

## Requirement → evidence matrix

| R-ID | Implemented by (file/commit) | Verified how | Status |
|------|------------------------------|--------------|--------|
| R1 | `tests/test_config.py` (a3cec28) | an audit hook over sandboxed and unsandboxed runs: all 28 test writes under the basetemp, none outside it except pytest's own; a positive control (reviewer); `gate.sh audit` (orchestrator) | ✅ |
| R2 | `tests/test_config.py` (a3cec28) | unsandboxed `--basetemp` runs: 75 passed on each Python, `/tmp/cmdkit` absent before and after (reviewer; `gate.sh R2`, orchestrator) | ✅ |
| R3 | `tests/test_config.py` (a3cec28) | the profile's `verify` passes with `/tmp` denied; the base fails to collect under the same denial (reviewer; `gate.sh tmpdenied`, orchestrator) | ✅ |
| R4 | `tests/test_config.py` (a3cec28) | two and four concurrent runs, overlapping in time, with 0 cross-run test-written paths (reviewer; `gate.sh concurrent`, orchestrator) | ✅ |
| R5 | `tests/test_config.py` (a3cec28) | identical 75 node IDs; the normalised diff shows only the location change (reviewer) | ✅ |
| R6 | `AGENTS.md` (a3cec28) | one commit touches both files; the `verify` row no longer names `/tmp/cmdkit/config` or a sandbox allowance (reviewer) | ✅ |

**Unmapped changes:** `issues/tests-use-tmp-path.md` changes `status` to `adopted:…` in `393d1ef`.
That's lifecycle bookkeeping.

## Findings

None.

These candidates were refuted with executed evidence:
- **Writes outside the basetemp:** all are pytest's own.
- **The "clear existing files" loop in `TestNamespace.test_from_local`,** which is now dead code: it
  calls only `os.remove`, the assertions are unchanged, and removing it would be restructuring,
  which the GOAL rules out.
- **`ROADMAP.md`'s entry,** which still describes the problem: it's accurate for `develop`, and
  retiring it is the roadmap step's job after landing.

## Human-gate triggers

None. There are no CONFIRMED findings, and no high-blast-radius path is touched.

## Optional completeness sub-pass (separate reviewer; may see TECH.md)

Not run.
