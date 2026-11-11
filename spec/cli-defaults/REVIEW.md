# REVIEW — Argument errors reach stderr by default; a group can opt in to help on a bare run

> Adversarial QA by `code-review`, run in an isolated/clean context (a subagent; where the runtime
> has none, `code-review`'s sequential fallback). The correctness pass grades the branch diff against
> [`GOAL.md`](GOAL.md) + the repo's `AGENTS.md` § Invariants **only** — it does not see
> `PLAN.md`/`TECH.md` (avoids grading-its-own-homework / plan-sycophancy). Every finding cites an
> **executed** command, not an assertion.

- **Reviewed commit:** 877a66634f1d0d51adbcc8bdd25006cdc2f1ad14  ·  **Base:** develop  ·  **Date:** 2026-11-11
- **Verdict:** changes-requested
- **Cycle:** 1 of ≤3. Mirrors `review.cycle` in `TECH.md`.

A single fresh reviewer graded the change. It saw `GOAL.md`, the rubric, `AGENTS.md`, the worktree,
and the spec-excluded diff. The GOAL's commits after the shape commit (`956fd6b`, `32413eb`) are
clarifications C1–C6, ruled at the GOAL and PLAN gates before the build.

## Verification run

- **The profile's `verify`,** with the sandbox off: 94 passed on Python 3.9 and 94 passed on 3.14.
- **The known `test_app_invalid_options` flake** didn't fire under random seeds. It reproduces with
  `--hypothesis-seed=24` (`opt='he'`, which argparse reads as `--help`), and it's seeded as deferred
  on the branch.
- **Subprocess drives** in fresh `python -I` interpreters: 25 logging setups × 7 argument-error
  targets, plus 12 bare-run targets, on Python 3.9, 3.12 and 3.14, each against HEAD and against the
  base tree (`b9efaca`). The reports agree across the three Pythons.
- **Import-time process-wide state** (loggers, handlers, `lastResort`, `disable`, the argparse
  version action, excepthook, streams, warnings filters) is identical on HEAD and base. Handler sets
  are unchanged across `main` in every run.
- **The docs:** Sphinx 7.4.7 builds on HEAD and on base with the same two third-party warnings. The
  new `ApplicationGroup.ALLOW_NOARGS` and `.main` anchors exist.
- **Mutants of `_last_resort_would_print`,** run against `tests/test_app.py` in a copy of the tree:
  - `no-isEnabledFor` and `always-report` are killed;
  - `no-lastResort-check`, `no-propagate-break` and `any-nullhandler` survive (F5).

## Requirement → evidence matrix

| R-ID | Implemented by (file/commit) | Verified how | Status |
|------|------------------------------|--------------|--------|
| R1 | `src/cmdkit/app.py` (8a59305) | with no logging configured, all 7 error targets give rc 2, empty stdout, and the message once on stderr; the C6 print cases print once. **F1:** three setups print it twice | ❌ |
| R2 | `src/cmdkit/app.py` (8a59305) | `basicConfig`, handlers on `cmdkit` or `cmdkit.app`, and `dictConfig` with a root handler are all byte-identical to base | ✅ |
| R3 | `src/cmdkit/app.py` (8a59305) | replaced on the class or on `Application`: called once, nothing on stderr, identical to base | ✅ |
| R4 | `src/cmdkit/app.py` (877a666) | `main([])` and `main(None)` equal `--help` output with rc 0. **F2:** a group with an optional `command` no longer calls `run` | ✅ as written; premise questioned |
| R5 | `src/cmdkit/app.py`, `tests/test_app.py` (877a666) | without the opt-in, usage and rc 1, identical to base; `test_app_group_usage` is unchanged | ✅ |
| R6 | `tests/test_app.py` | each opt-in's test sits beside a test pinning the default | ✅ |
| R7 | `src/cmdkit/app.py` | no new import-time effect; handler sets are unchanged across `main` | ✅ |
| R8 | `docs/api/app.rst`, docstrings | the status is corrected to `exit_status.usage`; the entries are added; Sphinx builds | ✅ |
| R9 | `AGENTS.md` (8a59305) | the line is removed in the same commit as the fix | ✅ |

**Unmapped changes:**
- `issues/test-invalid-options-help-prefix.md` and its `ROADMAP.md` entry: a legitimate deferral
  record (see F4).
- The `adopted:` status on `issues/cli-defaults.md`.

## Findings

### [MEDIUM/CONFIRMED] F1 · The message reaches stderr twice when cmdkit's own NullHandler is off the propagate walk
- **Where:** `src/cmdkit/app.py:48-57` (the walk) and `:164-165` (the write).
- **Failure scenario:** each of these setups leaves no handler on the walk at all:
  - `dictConfig({'version': 1, 'loggers': {'cmdkit': {'level': 'WARNING'}}})`, since naming
    `cmdkit` strips its handlers;
  - `logging.getLogger('cmdkit').handlers.clear()`;
  - `logging.getLogger('cmdkit.app').propagate = False`.

  Python's last resort prints the record, and cmdkit prints it again.
- **Evidence:** the `f1_min.py` probe on 3.14 gives HEAD `stderr_lines=2` and base `stderr_lines=1`.
  The matrix shows the same on 3.9, 3.12 and 3.14, for all 7 targets.
- **Touches:** R1 ("once"), and the Outcome's "no duplicate line".
- **Route (the property, both ways):** cmdkit writes the line exactly when cmdkit's own `NullHandler`
  is the only reason Python's last resort did not print the record. It never writes when Python
  already printed it, and never when the application silenced the record.

### [LOW/CONFIRMED] F3 · A filter on `cmdkit.app` that rejects the record doesn't stop the stderr write
- **Where:** `src/cmdkit/app.py:44-57`.
- **Failure scenario:** with a rejecting logger filter, Python would not reach `callHandlers`, so
  the last resort wouldn't print. HEAD writes the message anyway; base is silent.
- **Evidence:** the `filter-cmdkit.app` case.
- **Touches:** C6's defining sentence. It's the same property as F1, and routed with it.

### [LOW/CONFIRMED] F4 · The deferral seed misstates which option prefixes fail the test
- **Where:** `issues/test-invalid-options-help-prefix.md:18`.
- **Failure scenario:** the seed says prefixes of `--option` also fail the test. They raise
  `ArgumentError` ("expected one argument"), so the test passes for them. Only prefixes of `--debug`
  (DID NOT RAISE) and `--help` (`HelpOption`) fail.
- **Evidence:** a direct parse of each prefix on 3.14.

### [LOW/CONFIRMED] F5 · The suite doesn't pin C6's decisions on `propagate`, `lastResort` and which NullHandler counts
- **Where:** `tests/test_app.py:512-594`.
- **Failure scenario:** the mutants `no-lastResort-check`, `no-propagate-break` and
  `any-nullhandler` survive `tests/test_app.py` (47 passed). The shipped behaviour is correct by
  subprocess probe, but the suite wouldn't catch a regression.
- **Route:** a mutant sweep over every decision in `_last_resort_would_print`, each pinned by a test
  in the suite.

### [PLAUSIBLE] F2 · A group with an optional `command` and `ALLOW_NOARGS` now shows help instead of calling `run`
- **Where:** `src/cmdkit/app.py:231-232`.
- **Failure scenario:** a group whose `command` positional is `nargs='?'`, with `ALLOW_NOARGS = True`
  and a `run` that handles `command is None`. On 2.7.7 a bare run calls `run`, as the base docs
  describe ("proceed to its `run` method"). On HEAD it prints help and never calls `run`.
- **Evidence:** the `optgrpnoargs-empty` target. Base gives `stdout='default action\n'` with rc 0.
  HEAD gives the help text with rc 0. The same on 3.9, 3.12 and 3.14.
- **Touches:** R4's wording, and the GOAL's premise that the opt-in "today exits 2 in silence",
  which holds only when `command` is required. It is a possible default change under § Invariants 1.
  This finding is about the contract, so its triage is *fix* or *drop*, never *defer*.

## Human-gate triggers

- **F1** (CONFIRMED) is in `src/cmdkit/app.py`, a high-blast-radius path, and bears on
  § Invariants 1 and 3. **The maintainer's sign-off is required** before remediation or any later
  step. F3 shares F1's path.
- **F2** (PLAUSIBLE) needs the maintainer's triage.

## Optional completeness sub-pass (separate reviewer; may see TECH.md)

Not run.

## Maintainer's rulings (2026-11-11)

- **Human gate, F1:** the maintainer signed off. F1, F3, F4 and F5 are remediated as routed above.
- **F2 triage: fix.** R4 is narrowed: a bare run on a group with `ALLOW_NOARGS` shows help only when
  it would otherwise fail on the missing command. A group whose `command` is optional keeps calling
  `run`. This is recorded as a GOAL clarification.
