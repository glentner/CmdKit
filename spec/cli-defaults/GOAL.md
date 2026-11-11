# GOAL — Argument errors reach stderr, and a group can show its help when run bare

> **Origin spec.** The *what* and *why*: the locked contract the review grades against.
> The *how* lives in [`PLAN.md`](PLAN.md) and [`TECH.md`](TECH.md), written by the plan step.
> Edit requirements here; do **not** silently drift them during build.

- **slug:** cli-defaults
- **kind:** fix
- **appetite:** small

## Problem

**Argument errors are dropped.** `Application.main` catches an `ArgumentError` and hands it to
`cls.log_critical` (`src/cmdkit/app.py:125-127`), which defaults to the `critical` method of the
`cmdkit.app` logger (`app.py:63`). At import, cmdkit gives its `cmdkit` logger a `NullHandler`
(`src/cmdkit/__init__.py:33`). The record therefore always finds a handler, so Python's last-resort
handler, which would otherwise print it to stderr, never fires. In an application that hasn't
configured logging, every argument error is silent: an unknown flag, an unknown command in a group,
a missing positional. The program exits 2 and prints nothing, and its user can't tell what was
wrong. Probe on `develop` at `b9efaca`, Python 3.12, fresh interpreter, logging unconfigured:

| Call | Status | stdout | stderr |
|---|---|---|---|
| `Group.main(['bogus'])` (unknown command) | 2 | empty | empty |
| `Group.main(['cmd', '--bogus'])` (unknown flag in a command) | 2 | empty | empty |

This is an outright failure in the sense of `AGENTS.md` § Invariants 1: the documented behaviour has
an answer (report the error), and today the answer is lost. No test pins the silence; the tests
that reach `ArgumentError` (`test_app_noargs`, `test_app_invalid_number_of_positional`,
`test_app_invalid_options`, `test_app_group_noargs` in `tests/test_app.py`) call `from_cmdline`,
which raises, and never `main`.

**A bare group can't show its help.** Run with no arguments, an `ApplicationGroup` prints its usage
and exits 1 (`app.py:103-108`), and `tests/test_app.py::test_app_group_usage` pins that. A group
author who would rather show the full help has no way to ask for it. Setting `ALLOW_NOARGS = True`
on the group, the switch a plain `Application` uses to run with no arguments, makes it worse: the
group's `command` positional is required, so the parse fails and the group exits 2, silently (the
first problem). Probe as above: `ALLOW_NOARGS` group, `main([])` → status 2, stdout and stderr
empty.

Both defects are pre-existing: the lines involved date from 2019–2023, before this repo adopted its
current workflow.

## Outcome / vision

A user who mistypes a flag or a command sees why the program refused it, on stderr, even when the
application never configured logging; the exit status is the one it is today. An application that
does configure logging, or routes cmdkit's messages through its own `log_critical`, sees exactly
what it sees today: no duplicate line, no new output.

~~A group author can set `ALLOW_NOARGS = True` and have the group print its help and exit 0 when
run bare without the command it requires (C7).~~ **Out of scope (C9):** moved to
`issues/group-noargs-help.md`. A bare group, with or without that setting, behaves as it does in
2.7.7, apart from R1 reporting any argument error it meets.

## Acceptance criteria (the contract)

"No logging configured", below, means: the application hasn't replaced `log_critical`, and no
handler other than the `NullHandler` cmdkit attaches at import would receive a record logged to
`cmdkit.app`.

- **R1** — WHILE no logging is configured, WHEN `Application.main` (or `ApplicationGroup.main`)
  catches an `ArgumentError`, the error's message SHALL be written to stderr, once, as the bare
  message text followed by a newline (C1); `main` SHALL return `exit_status.bad_argument` (2), as
  today; and nothing SHALL be written to stdout. This covers at least an unknown command in a group, an
  unknown flag, and a missing required positional, at the top level and inside a group's command.
  When `sys.stderr` is `None` the message is not written, and a failure to write it (`OSError`,
  `ValueError`) is swallowed; `main` still returns 2 and writes nothing to stdout (C10).
- **R2** — WHILE a logging handler other than cmdkit's `NullHandler` would receive a record logged
  to `cmdkit.app` (for example after `logging.basicConfig`), WHEN `main` catches an
  `ArgumentError`, the configured handlers SHALL receive exactly what they receive today (one
  `CRITICAL` record carrying the message), and cmdkit SHALL write nothing further to stderr or
  stdout. The exit status SHALL be unchanged.
- **R3** — IF the application has replaced `log_critical` (on its class or on `Application`), THEN
  WHEN `main` catches an `ArgumentError`, the replacement SHALL be called once with the error, as
  today, and cmdkit SHALL write nothing further to stderr, whether or not any handler stands behind
  the replacement (C2).
- **R4** — **Out of scope (C9):** moved, with C7 and C8, to `issues/group-noargs-help.md`; kept
  here as the record, and not graded in this cycle. WHEN an `ApplicationGroup` subclass with `ALLOW_NOARGS = True` runs with an empty
  effective command line (`main([])`, or `main(None)` with no arguments in `sys.argv`; C8), and the
  group's interface would reject that bare command line, as it does when the `command` positional is
  required (C7, C8), it SHALL print to stdout exactly what `main(['--help'])` prints for that group
  and SHALL return `exit_status.success` (0), with nothing on stderr. A group whose `command`
  positional is optional SHALL call `run` on a bare run exactly as in 2.7.7 (C7). Under the opt-in,
  `main(None)` SHALL parse `sys.argv[1:]` exactly as in 2.7.7, so arguments there dispatch or are
  reported as an argument error as in 2.7.7, and never show the help in their place (C8).
- **R5** — WHEN an `ApplicationGroup` runs with an empty command line (`main([])`, or
  `main(None)`, whatever `sys.argv` holds), with or without `ALLOW_NOARGS = True`, it SHALL behave
  exactly as in 2.7.7 apart from R1 applying to any `ArgumentError` it raises (C9): without the
  opt-in it prints its usage and returns `exit_status.usage` (1) (`test_app_group_usage` keeps
  passing unchanged); with it, the command line is parsed, dispatched and handled as 2.7.7 does
  (help and version options, the group's `exceptions` map, and `run` included). A plain
  `Application`'s bare-run behaviour, with and without `ALLOW_NOARGS`, SHALL be unchanged apart
  from R1 applying to any `ArgumentError` it raises.
- **R6** — Each new behaviour SHALL land with a test pinning the default beside the test of the new
  behaviour (`AGENTS.md` § Invariants 1): R1's test sits beside tests of R2 and R3 (C9; R4's
  test left with R4).
- **R7** — The fix SHALL keep to `AGENTS.md` § Invariants 4 on import-time effects: importing cmdkit
  adds no process-wide effect it doesn't have today. Whether R1's message is written SHALL be
  decided when `main` catches the error, and no handler SHALL stay attached afterwards (C1).
- **R8** — The docstrings of the touched members, and `docs/api/app.rst`, SHALL describe the
  behaviour as shipped: `ALLOW_NOARGS` on a plain application, and the default reporting of
  argument errors (R1–R3) under `log_critical`. The `ALLOW_NOARGS` paragraph's stated status for a
  bare run, `exit_status.success` today, SHALL be corrected to the status `main` returns
  (`exit_status.usage`) (C4). Nothing SHALL document a bare-group help (C9).
- **R9** — `AGENTS.md` § Invariants 3's known-limitation line ("with no logging configured,
  `ArgumentError` messages are dropped") SHALL be removed in the same commit as the fix (C5).

**How it is shown.**

1. R1 in a fresh interpreter with logging unconfigured, for each case R1 names: status 2, stdout
   empty, stderr carrying the message once (for the unknown command, the string `bogus`). pytest's
   logging plugin attaches its own handlers to the root logger during a test, so an in-process test
   of R1 has to account for them; the plan chooses how.
2. R2 after `logging.basicConfig` (or with `caplog`): one `CRITICAL` record with the message, and
   no extra stderr output from cmdkit.
3. R3 with a replaced `log_critical` that records its calls: one call, and stderr empty.
4. **Out of scope (C9), with R4; R5 is shown by a bare group's `main([])` and `main(None)`
   matching 2.7.7's output and status in every case C9 names.** R4 and R5 side by side: an
   `ALLOW_NOARGS` group's `main([])`, and its `main(None)` with no
   arguments in `sys.argv`, print its `--help` output and return 0; `test_app_group_usage` passes
   unchanged. With `sys.argv` carrying arguments (`['app', 'bogus']`), its `main(None)` reports the
   argument error with status 2, as in 2.7.7 (C8). An `ALLOW_NOARGS` group
   whose `command` positional is optional (`nargs='?'`) calls its `run` on a bare run, with the
   output and status 2.7.7 gives (C7).
5. R7: the set of handlers on the `cmdkit`, `cmdkit.app` and root loggers after `import cmdkit` in
   a fresh interpreter is the same as at `b9efaca`, and is still the same after a `main` call that
   hits R1.

## Non-goals (no-gos)

- **`main(None)` reading `sys.argv`.** `main` treats `None` as an empty command line and never reads
  `sys.argv`; the documented call is `main(sys.argv[1:])`. Reading `sys.argv` by default would
  change a default, so it stays as it is. Under `ALLOW_NOARGS`, 2.7.7 already parses `sys.argv[1:]`
  for `None` (argparse's default), and that stays as it is too (C8).
- **The exit statuses.** Every path keeps its `ExitStatus` value. (Before C9, the opt-in in R4 was
  to return a different one, from a configuration that today exits 2 in silence.)
- **A bare group's help (R4, C7, C8)** moves to its own cycle, `issues/group-noargs-help.md` (C9).
- **The helper's fidelity to `Logger.handle` in contrived setups** (a filter that keeps state or
  reads caller fields, filters on `logging.lastResort` itself): `issues/last-resort-filter-fidelity.md`
  (C9).
- **Suggestions for a mistyped command** (`did you mean …`): that is the next roadmap cycle,
  `issues/cli-command-suggestions.md`, which edits the same message after this one lands.
- **Group exception-handler isolation** (`issues/app-exception-handlers.md`) and **argparse's
  generated help as a fallback** (`issues/argparse-help-fallback.md`): later cycles that build on
  this one.
- **The `KeyboardInterrupt` message** (`keyboard-interrupt: going down now!`, `app.py:129-131`).
  It goes through the same `log_critical` and is dropped the same way with no logging configured;
  it stays as it is, exit status 4 included, and no seed is recorded for it (C3).
- **The `uncaught exception occurred!` path.** `main` logs it through `log_exception` and re-raises,
  so the interpreter already prints the traceback.
- **`Interface` itself** (`src/cmdkit/cli.py`): it keeps raising and never printing (§ Invariants 3).
- **The build files and `tests/test_config.py`**, which open PRs #30 and #31 change.

## Clarifications

Rulings at shaping (2026-11-10):

- **Q:** Kind and appetite? — **A:** `fix`, `small`, from the seed's frontmatter (resolved
  2026-11-10).
- **Q:** Is the dropped message an outright failure, fixed by default? — **A:** Yes. With no
  logging configured, an `ArgumentError` message reaches stderr and the exit status stays as it is
  today. Applications that configure logging see no change in what their handlers receive (resolved
  2026-11-10; R1, R2).
- **Q:** Is a bare group's help-and-exit-0 the default or an opt-in? — **A:** Opt-in, through
  `ALLOW_NOARGS` on the group, which today gives a silent exit 2. The default (usage, exit 1,
  pinned by `test_app_group_usage`) is unchanged (resolved 2026-11-10; R4, R5).
- **Q:** Do opt-ins need a test pinning the default? — **A:** Yes, beside the test of the new
  behaviour, per § Invariants 1 (resolved 2026-11-10; R6).
- **Q:** Does `main(None)` start reading `sys.argv`? — **A:** No (resolved 2026-11-10; Non-goals).

Raised during shaping, ruled 2026-11-10:

- **C1 · Q:** In what form does R1's message reach stderr, and from where? (a) The bare message
  text and a newline, as Python's last-resort handler would print it; (b) argparse's form,
  `{prog}: error: {message}`; (c) a cmdkit logging style. A handler cmdkit attaches, or a write in
  `main`? — **A:** (a), the bare message and a newline. Whether to write it is decided at call time
  in `main`'s `ArgumentError` path, with no persistent handler attached; the exact code is the
  plan's (resolved 2026-11-10; R1, R7).
- **C2 · Q:** When the application replaces `log_critical` but configures no handler behind it,
  does cmdkit still write to stderr? — **A:** No. The replacement wins, and cmdkit writes nothing
  to stderr (resolved 2026-11-10; R3).
- **C3 · Q:** Is the dropped `KeyboardInterrupt` message (`app.py:129-131`) in scope? — **A:** No.
  It is a non-goal, and no seed is recorded for it (resolved 2026-11-10; Non-goals).
- **C4 · Q:** Does R8 correct the bare-run status that the `ALLOW_NOARGS` paragraph of
  `docs/api/app.rst` states (`exit_status.success`, where `main` returns `exit_status.usage`)? —
  **A:** Yes: the cycle rewrites that paragraph anyway (resolved 2026-11-10; R8).
- **C5 · Q:** Does this cycle remove the known-limitation line from `AGENTS.md` § Invariants 3, a
  human-gated section? — **A:** Yes. Removing a recorded known limitation once its fix lands is how
  § Invariants evolves, and sign-off of this GOAL covers it (resolved 2026-11-10; R9).

Raised at the PLAN/TECH sign-off, ruled 2026-11-10:

- **C6 · Q:** "No logging configured" is defined above R1 as no handler other than cmdkit's
  `NullHandler` *would receive* the record. Read literally, that writes the bare line in setups an
  application uses to silence logging: `logging.config.dictConfig` with its default
  `disable_existing_loggers` (which disables the `cmdkit.app` logger when cmdkit was imported
  first), `logging.disable(logging.CRITICAL)`, and handlers whose levels sit above `CRITICAL`. Is
  that intended? — **A:** No. "No logging configured" means Python's own last-resort handler would
  have printed this `CRITICAL` record if cmdkit's own `NullHandler` were not there. All of these
  must hold: logging isn't disabled at `CRITICAL` (`logging.disable`); the `cmdkit.app` logger is
  enabled for `CRITICAL`, and not disabled (by `dictConfig` or otherwise); and the walk up the
  `propagate` chain finds no handler other than cmdkit's own `NullHandler`, counting handlers the
  way `Logger.callHandlers` counts them for its last-resort decision, whatever each handler's
  level. So the three setups above stay silent, as in 2.7.7, while `propagate = False` on the
  `cmdkit` logger with no handler of the application's on it prints, exactly as Python would. The
  replacement rule (C2) is unchanged. Rationale: cmdkit's `NullHandler` suppresses the last
  resort, and this fix restores what Python would have done without it; anything an application
  did to silence cmdkit stays silent, so no default a consumer relies on changes (§ Invariants 1)
  (resolved 2026-11-10; R1, R2, R3).

Raised at review cycle 1 (finding F2), ruled 2026-11-11:

- **C7 (2026-11-11, R4, F2) · Out of scope (C9),** with R4: kept as the record for
  `issues/group-noargs-help.md`. **Q:** In 2.7.7, a group whose `command` positional is optional
  (`nargs='?'`) and that sets `ALLOW_NOARGS = True` calls its `run` on a bare run, as the docs
  describe ("proceed to its `run` method"). R4 as first worded shows the group's help instead. Which
  holds? — **A:** A bare run (`[]` or `None`) on a group with `ALLOW_NOARGS = True` shows its
  `--help` output and returns 0 *only when the run would otherwise fail on the missing command*. A
  group whose `command` positional is optional calls `run` exactly as on 2.7.7. The Non-goals'
  premise, that the opt-in "today exits 2 in silence", then holds for every group R4 changes
  (resolved 2026-11-11; R4).

Raised at the PLAN/TECH sign-off of the review cycle 1 revision, ruled 2026-11-11:

- **C8 (2026-11-11, R4) · Out of scope (C9),** with R4: kept as the record for
  `issues/group-noargs-help.md`. **Q:** R4 called `main(None)` a command line `main` "already treats as
  empty". Under `ALLOW_NOARGS`, 2.7.7 passes `None` to argparse, which parses `sys.argv[1:]`. Does
  R4 keep that, and what does "would otherwise fail on the missing command" (C7) mean in the code?
  — **A:** `main(None)` parses `sys.argv[1:]` exactly as in 2.7.7. R4's bare-run rule applies when
  the effective command line is empty: `[]`, or `None` with no arguments in `sys.argv`. A non-empty
  `sys.argv` under `None` dispatches, or is reported as an argument error, as in 2.7.7, and never
  shows the help in its place. C7's condition is read as the plan's deviation row 3 reads it, and
  the review grades against this reading: under the opt-in, a bare run that the group's interface
  would reject shows the help; one it accepts proceeds as in 2.7.7. For a group whose only
  required argument is `command`, the two readings are the same. A group whose `command` is
  optional but which requires some other argument shows its help on a bare run too, rather than
  that argument's error (resolved 2026-11-11; R4).

Ruled at the escalation after review cycle 2, 2026-11-11:

- **C9 (2026-11-11, R4, R5, R6, R8, C6, C7, C8) · Q:** Review cycle 2 did not converge. The bare-group
  help kept breaking 2.7.7's handling of `main(None)` (help and version options and action
  exceptions escaped `main`; arguments in `sys.argv` showed the help in place of their error), and
  the report counted an application's own `NullHandler` on the `cmdkit` logger as cmdkit's. What
  ships in this cycle? — **A:** The cycle is split.
  - **Moved out:** R4, C7 and C8 leave this cycle for `issues/group-noargs-help.md`, a feature of
    its own, designed around the effective command line. They stay above, marked out of scope, as
    the record. `ApplicationGroup`'s bare-run behaviour is exactly 2.7.7's (R5, narrowed); R6 and
    R8 keep only what remains: R1's test beside R2's and R3's, and the docs' `exit_status.usage`
    correction for a plain application (C4), with no bare-group help documented.
  - **Which `NullHandler` is cmdkit's (review cycle 2, F3):** cmdkit's own `NullHandler` is the one
    `src/cmdkit/__init__.py` creates, recognised by a mark set on it there; no other `NullHandler`
    counts as cmdkit's, whatever its type or logger. An application's own `NullHandler` on the
    `cmdkit` logger, added programmatically or by the `dictConfig` recipe that routes `cmdkit` to a
    `NullHandler` with `propagate: False`, is a handler of the application's: the line stays
    silent, as in Python and in 2.7.7. Setting the mark adds no process-wide effect (R7, § Invariants
    4).
  - **Deferred (review cycle 2, F4):** the report's fidelity to `Logger.handle` in contrived setups
    (its filter check runs on a record cmdkit builds, and `logging.lastResort`'s own filters are not
    consulted) moves to `issues/last-resort-filter-fidelity.md`.
  - The rest stands: R1–R3, R6–R9 and C1–C6 (resolved 2026-11-11; R4, R5, R6, R8, C6).

Ruled at the escalation after review cycle 3, 2026-11-11 (a scoped fourth cycle):

- **C10 (2026-11-11, R1, CR-F1) · Q:** R1's write to stderr has none of the error handling Python's
  last-resort handler has. With stderr a pipe whose reader has exited, `main` raises
  `BrokenPipeError` instead of returning 2; with `sys.stderr` set to `None` after import, the
  message goes to stdout. What does R1 require there? — **A:** The report is skipped when
  `sys.stderr` is `None`, and a failure writing it (`OSError`, `ValueError`) is swallowed, as
  Python's last resort does: `main` still returns `exit_status.bad_argument` (2), and nothing goes
  to stdout. Nothing else in R1–R3 changes (resolved 2026-11-11; R1).

## Related materials

- Seed: `issues/cli-defaults.md`; `ROADMAP.md` Part IV, order 11.
- Files: `src/cmdkit/app.py` (lines 58, 63, 94–138); `src/cmdkit/__init__.py` (line 33);
  `src/cmdkit/cli.py` (`Interface.error` and `exit`, lines 94–100); `tests/test_app.py`
  (`test_app_group_usage`, the `Group` fixture); `docs/api/app.rst` (`ALLOW_NOARGS`,
  `log_critical`); `AGENTS.md` § Invariants 1, 3 and 4.
- Python's last-resort handler: <https://docs.python.org/3/library/logging.html#logging.lastResort>.
- Configuring logging for a library: <https://docs.python.org/3/howto/logging.html#configuring-logging-for-a-library>.
