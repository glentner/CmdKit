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

## Review cycle 2 — changes-requested (2026-11-11)

**Reviewed commit:** 4645372cfe1b36e329a8149bf471bac43cc05ea8. A fresh, full blind pass over the
whole spec-excluded diff, graded against GOAL C1–C8. It saw neither the cycle-1 review nor its files.

### Verification run
- **The profile's `verify`,** with the sandbox off: 121 passed on Python 3.9.25 and 121 on 3.14.6.
- **Subprocess drives** against HEAD and base (`b9efaca`), on 3.9 and 3.14:
  - 58 C6 setups: 112 of 116 runs match the last-resort reference. The no-handler walks now print
    exactly once, so cycle 1's F1 is fixed.
  - R4/C7/C8 groups through `main([])` and through `main(None)` with varied `sys.argv`.
  - An § Invariants 3 drive.
- **Import-time and post-`main` state** equals 2.7.7 (R7 is met).
- **Mutation sweep** over 41 mutants on copies: 37 killed. The survivors are G07, G12, G09, and
  G08, which is equivalent.
- **The docs:** Sphinx builds on HEAD and base with the same warnings.

### Findings

#### [CRITICAL/CONFIRMED] F1 · Exceptions escape `ApplicationGroup.main` under `ALLOW_NOARGS` with `main(None)`
- **Where:** `src/cmdkit/app.py:244-248`.
- **Failure scenario:** a group with `ALLOW_NOARGS`, called as `main(None)` with `sys.argv` holding
  `--help` or `-h`, raises `HelpOption` out of `main`. With `--version` it raises `VersionOption`.
  With a custom action that raises, the exception escapes and the group's `exceptions` map is
  bypassed. In each case 2.7.7 printed help or the version and returned 0, or mapped the exception
  or logged it and re-raised.
- **Evidence:** `r4.log` and `inv3.log` on 3.9 and 3.14.
- **Touches:** § Invariants 3 (`main` returns an `int`; an unhandled exception is logged and
  re-raised) and C8.

#### [HIGH/CONFIRMED] F2 · `main(None)` with arguments in `sys.argv` prints help where 2.7.7 reports the argument error
- **Where:** `src/cmdkit/app.py:244-248`, and the docs at `docs/api/app.rst:256-258` and
  `app.py:231`.
- **Failure scenario:** `NGroup.main(None)` with `['app','cmd','x']` or `['app','--bogus']`, and the
  same for an optional-command group or one with `ALLOW_PARSE`, prints help and returns 0. 2.7.7
  reports the error and returns 2. `sys.argv` is also parsed twice, so a side-effecting action runs
  twice.
- **Evidence:** `r4.log`.
- **Touches:** R4, C7, C8, and R8, since the docs promise otherwise.

#### [MEDIUM/CONFIRMED] F3 · The application's own `NullHandler` on `cmdkit` is treated as cmdkit's
- **Where:** `src/cmdkit/app.py:55-56`, pinned by `tests/test_app.py:693`.
- **Failure scenario:** the common `dictConfig` recipe routes `cmdkit` to a `NullHandler` with
  `propagate: False`. Under it, HEAD prints the line, while 2.7.7 and Python's last-resort reference
  are silent. A programmatic `addHandler(NullHandler())` on `cmdkit` behaves the same way.
- **Evidence:** `c6.log`.
- **Touches:** C6 ("anything an application did to silence cmdkit stays silent") and § Invariants 1.
  This is the setup the plan's deviation row 2 accepted, and the review shows it contradicts C6.

#### [LOW/CONFIRMED] F4 · The helper diverges from `Logger.handle` and `callHandlers` in contrived setups
- **Where:** `src/cmdkit/app.py:48-50`.
- **Failure scenario:** the helper re-runs logger filters on a synthetic record, which differs in
  `funcName`, `lineno` and dedupe state, and it ignores filters on `lastResort`.
- **Evidence:** `c6.log`.

#### [LOW/CONFIRMED] F5 · No test pins `ApplicationGroup.main` passing `shared` through
- **Where:** `src/cmdkit/app.py:249`.
- **Failure scenario:** mutant G09 drops `shared=shared`, and the suite stays green. That mutant
  breaks nested-group shared options, which are reachable 2.7.7 behaviour (`shared_nested.log`).

### Human-gate triggers
- F1, F2 and F3 are CONFIRMED in `src/cmdkit/app.py`, a high-blast-radius path, and F1 violates a
  `[human gate]` section (§ Invariants 3).
- This is the second review cycle without convergence, so the cycle escalates to the maintainer.

## Maintainer's ruling on the cycle-2 escalation (2026-11-11)

**The cycle is split.**
- **Kept:** the stderr report (R1–R3, R6–R9; C1–C6) ships in this cycle, with these fixes:
  - F3 is fixed by marking cmdkit's own `NullHandler` where `__init__.py` creates it, and
    recognising it by that mark.
  - F4 is deferred to a seed.
- **Moved out:** the bare-group help (R4, C7, C8) leaves this cycle. `ApplicationGroup`'s bare-run
  behaviour returns to 2.7.7's, and the feature moves to a new seed for its own cycle, designed
  around the effective command line rather than a pre-parse. Cycle 2's F1, F2 and F5 leave with it.
- **The next review is cycle 3, the last one allowed.**
