# PLAN — Argument errors reach stderr, and a group can show its help when run bare

> **Status:** Draft for review · **Last updated:** 2026-11-11
> **Authoritative technical design.** The *how*. Vision/contract is [`GOAL.md`](GOAL.md);
> the phased executable roadmap is [`TECH.md`](TECH.md). Backing detail is in
> [`research/`](research/). Every design element traces to a GOAL R-ID.

## 1. Summary

Two small changes to `src/cmdkit/app.py`. In `Application.main`'s `ArgumentError` branch, after
calling `log_critical` as today, cmdkit writes the bare message to `sys.stderr` when
`log_critical` is still the default and cmdkit's own `NullHandler` is the only reason Python's
last-resort handler did not print the record (GOAL C6); the decision is a walk of the handler chain
at the moment of the error, and nothing is attached. And
`ApplicationGroup` gains a `main` that turns an empty command line into `['--help']` when the group
sets `ALLOW_NOARGS = True` and its interface rejects the bare command line (GOAL C7), so a bare
group that requires its command prints exactly its `--help` output and returns 0. Two phases, one
per behaviour, each with its tests and docs; the `AGENTS.md` line goes with the first.

**Revised after review cycle 1 (2026-11-11).** The review found the helper writing a second line
where no handler is found at all and Python's last resort has printed the record (F1), ignoring a
filter on `cmdkit.app` that rejects it (F3), and a suite that leaves three of the helper's decisions
unpinned (F5); and the bare-group opt-in overriding a group whose `command` is optional (F2, ruled
as C7). This revision redesigns the helper and the group's `main` (§ 2), adds suite tests for every
decision and a mutant sweep that grades them (§ 6), reopens P1 for F1, F3 and F5 and P2 for F2
(`TECH.md`), and corrects the deferral seed (F4). The sections below describe the design as
revised; § 4 and § 6 keep the record of the first plan.

## 2. Design

### Argument errors (`src/cmdkit/app.py`, `Application.main`)

The `except ArgumentError` branch becomes:

```python
except ArgumentError as error:
    cls.log_critical(error)
    if cls.log_critical == log.critical and _hidden_by_null_handler(log, logging.CRITICAL, error):
        print(error, file=sys.stderr)
    return exit_status.bad_argument
```

- **Replacement test (R3, C2).** `cls.log_critical == log.critical` holds only while the class
  resolves `log_critical` to the default, the `critical` bound method of the `cmdkit.app` logger
  (bound methods compare equal on the same function and the same logger object). A function or
  `staticmethod` on the class, a function assigned to `Application.log_critical`, or another
  logger's `critical` all compare unequal, and then cmdkit writes nothing, whether or not a handler
  stands behind the replacement.
- **Last-resort test (R1, R2; C6), a private module function**
  `_hidden_by_null_handler(logger, level, msg) -> bool`, which replaces cycle 1's
  `_last_resort_would_print`. It is true exactly when cmdkit's own `NullHandler` is the only
  reason Python's last resort did not print the record: it follows `Logger.handle` and
  `Logger.callHandlers` in order, and returns false wherever Python would print nothing anyway, and
  wherever Python already printed the record because no handler was found at all (review F1, F3).
  A module-level function whose body is verbatim, at this indentation, below its docstring (the
  `mutants` gate anchors on these lines):

  ```python
  def _hidden_by_null_handler(logger: logging.Logger, level: int, msg: object) -> bool:
      """..."""
      if not logger.isEnabledFor(level):
          return False
      if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, msg, (), None)):
          return False
      if logging.lastResort is None or level < logging.lastResort.level:
          return False
      found = False
      current = logger
      while current is not None:
          for handler in current.handlers:
              if current.name != 'cmdkit' or type(handler) is not logging.NullHandler:
                  return False
              found = True
          if not current.propagate:
              break
          current = current.parent
      return found
  ```

  1. **Enabled.** False if `not logger.isEnabledFor(level)`: `logging.disable`, a logger level
     above `level`, and `logger.disabled` (what `dictConfig` sets on loggers it disables). Python
     never builds the record then.
  2. **Filters (F3).** False if the logger's own filters reject a record built the way
     `Logger._log` builds it (`makeRecord`, the message `msg`, no arguments): `Logger.handle`
     returns before `callHandlers` then, so nothing prints. Python consults only the logging
     logger's filters, never a parent's, and neither does this.
  3. **Last resort.** False if `logging.lastResort` is `None` or its level is above `level`.
  4. **The walk.** The logger and its ancestors while `propagate` holds. Any handler found,
     whatever its level, other than an exact `logging.NullHandler` on the logger named `cmdkit`,
     is the application's: false. Each of cmdkit's own counts as found.
  5. **No handler at all (F1).** If the walk found none, `callHandlers` handed the record to the
     last resort, which printed it: false, so the line appears once, Python's. That covers
     `dictConfig` naming `cmdkit` (it strips the logger's handlers), `cmdkit`'s handlers cleared,
     and `propagate = False` on `cmdkit.app`.

  So an application that silenced cmdkit (`dictConfig`'s default, `logging.disable`, a rejecting
  filter, handlers levelled above `CRITICAL`, `lastResort = None`) stays silent, `propagate = False`
  on `cmdkit` with no handler of the application's there prints cmdkit's line, as Python would
  without the `NullHandler`, and no setup gets two lines.
  ([research/01](research/01-call-time-decision.md))
- **The write (C1).** `print(error, file=sys.stderr)`: `str(error)` and a newline, the form
  Python's last-resort handler uses, with `sys.stderr` looked up at call time (so `capsys` and any
  redirect see it). It runs after `log_critical`, at most once per caught error. A group delegates
  to its command's own `main`, which reports its own error; the group then returns the command's
  status through `CompletedCommand` and never reports it again, so a nested error is written once.
- **Not touched:** the `KeyboardInterrupt` branch (C3, a non-goal: it stays silent with no logging
  configured), the uncaught-exception branch, `Interface` (`cli.py`), `__init__.py` and its
  `NullHandler`. `app.py` gains `import sys` in its standard-libs group; there is no new import-time
  effect.

### A bare group (`src/cmdkit/app.py`, `ApplicationGroup.main`)

```python
@classmethod
def main(cls, cmdline: List[str] = None, shared: Namespace = None) -> int:
    if not cmdline and cls.ALLOW_NOARGS is True:
        try:
            cls.interface.parse_args(cmdline)
        except ArgumentError:
            cmdline = ['--help', ]
    return super(ApplicationGroup, cls).main(cmdline, shared=shared)
```

The body is verbatim (the `mutants` gate anchors on it). **Only when the bare run would fail
(C7, review F2).** The group's own interface parses the command line it was given first, exactly
as the bare run would (`[]`; or `None`, which argparse reads from `sys.argv`, as
`from_cmdline(None)` does on 2.7.7 under the opt-in); `Interface` raises `ArgumentError` and never
prints, and nothing is kept. When the parse fails (the `command` positional is required, as in every
group in the docs and tests, and nothing supplies it), the bare run becomes `--help`. When it
succeeds (`command` is `nargs='?'`, or `sys.argv` carries arguments for a `None`), `cmdline` is
passed on unchanged and `Application.main` runs as in 2.7.7: it parses and calls `run`, which
handles `command is None` or dispatches, or reports the argument error per R1. The adversarial
review of this revision found the first draft parsing `[]` for a `None`, which showed the help (status
0) for `sys.argv` `['app', 'bogus']` where 2.7.7 reports the error.

For a group that requires its command, `main([])`, `main(None)` and `main()` then follow
`main(['--help'])` exactly: `from_cmdline`
parses `--help`, `Interface` raises `HelpOption`, `handle_help` prints the help text and `main`
returns `exit_status.success`. That holds with `ALLOW_PARSE` too (it skips its own parse when
`--help` is present) and for a group nested as another group's command. Without the opt-in the
condition is false and `Application.main` runs unchanged: usage, `exit_status.usage` (R5).
`from_cmdline` is not changed, so a direct `from_cmdline([])` still raises `ArgumentError`
(`test_app_group_noargs`). A plain `Application` keeps `Application.main` as it is.

### Docs (`docs/api/app.rst`, docstrings)

- `Application.main`'s docstring says how an argument error is reported; `ApplicationGroup.main`
  gets a docstring of its own (R8).
- The `log_critical` / `log_exception` paragraph says the default also writes the bare message to
  stderr when Python's last resort would have printed it (no handler of the application's, and
  nothing silencing the logger), and that an override alone handles the message.
- The `ALLOW_NOARGS` paragraph's bare-run status becomes `exit_status.usage` (C4) and it says what
  the attribute does on a group; `ApplicationGroup`'s section gains an `ALLOW_NOARGS` entry.
- Review cycle 1: the `log_critical` paragraph and `Application.main`'s docstring say the line is
  written when cmdkit's `NullHandler` is the only reason the last resort stayed quiet, that Python's
  own line stands alone where no handler is found, and that a rejecting filter on `cmdkit.app`
  keeps it silent (P1). Both `ALLOW_NOARGS` entries and `ApplicationGroup.main`'s docstring say the
  help is shown only for a group whose interface rejects an empty command line, and that a group
  whose `command` is optional proceeds to `run` (P2).

### `AGENTS.md`

§ Invariants 3 loses exactly its last bullet, the recorded limitation about dropped `ArgumentError`
messages, in the commit that changes `Application.main` (R9). Nothing else in the file changes;
the open sibling changes edit other lines (the profile's `verify` row, the release recipe, the
high-blast-radius list, § Invariants 4), so the edits do not overlap.

### Tests (`tests/test_app.py`)

- A context manager in the module, `no_logging_configured()`, hides the root logger's handlers
  inside a test body (pytest's logging plugin puts four there) and restores them in place
  ([research/02](research/02-pytest-logging.md)).
- R1: parametrized over an unknown flag and a missing positional at the top level and inside a
  group's command, plus an unknown command in a group: status 2, stdout empty, stderr exactly the
  message (taken from `from_cmdline`'s own `ArgumentError`) and a newline.
- R2 beside it: with `caplog`, one `CRITICAL` record from `cmdkit.app`, stdout and stderr empty.
- R3 beside it: `log_critical` replaced on the group class, and on `Application`, by a recorder:
  one call, stderr empty, with no handler behind it.
- C6 beside them: with `logging.disable(logging.CRITICAL)` in force (and no handler), stderr stays
  empty. Cycle 1 left the remaining C6 setups to the gate's fresh-interpreter drive; the review
  cycle 1 table below pins them in the suite too.
- R7: the handler lists of `cmdkit`, `cmdkit.app` and root are the same before and after a call
  that reports on stderr.
- R4 beside R5: an `ALLOW_NOARGS` group's `main([])` and `main(None)` print what its
  `main(['--help'])` prints and return 0, placed after `test_app_group_usage`, which stays
  byte for byte; `Group.main(None)` prints usage and returns 1.
- R5, plain application: `ALLOW_NOARGS` with no required argument runs and returns 0; with a
  required positional, the bare run is an `ArgumentError`, reported on stderr per R1.
- **Review cycle 1, every decision pinned in the suite (F1, F3, F5).** One parametrized test runs
  `Group.main(['bogus'])` under `no_logging_configured()` for each setup below and asserts stdout
  empty, status 2, and stderr either exactly the message and a newline (`once`) or empty
  (`silent`); setups go through `monkeypatch` (or a finalizer that calls `setLevel`, so the
  logger's level cache is cleared) and are undone after the test.
  - `once`: unconfigured; `cmdkit`'s handlers emptied and `propagate = False` on `cmdkit.app`
    (no handler at all: Python's line, not cmdkit's); `propagate = False` on `cmdkit` with a root
    handler; a second plain `NullHandler` on `cmdkit`; an accepting filter on `cmdkit.app`;
    `lastResort` at exactly `CRITICAL`; `cmdkit.app` and `lastResort` at `ERROR`.
  - `silent`: a rejecting filter on `cmdkit.app`; `cmdkit.app` disabled; `cmdkit.app` levelled
    above `CRITICAL`; `lastResort = None`; `lastResort` levelled above `CRITICAL`; a `NullHandler`
    on root; a `NullHandler` on `cmdkit.app`; a `NullHandler` subclass on `cmdkit`; a root handler
    levelled above `CRITICAL`.
- **Review cycle 1, the optional command (F2, C7), beside R4 and R5.** A group whose `command` is
  `nargs='?'` and whose `run` prints a default action when `command is None`: without the opt-in,
  `main([])` prints usage and returns 1; with `ALLOW_NOARGS`, `main([])` and `main(None)` (with
  `sys.argv` patched to the program name alone, since `from_cmdline(None)` reads it, as in 2.7.7)
  call `run` and return 0, nothing on stderr.
- **The adversarial review's additions.** Three more setups in the table: a filter on `cmdkit.app`
  that rejects records naming `bogus` (`silent`), one that passes `CRITICAL` only (`once`), and
  `logging.Filter('cmdkit.app')` (`once`), so the probe record's message, level and logger name
  are pinned. A `log_critical` replaced by another logger's `critical`: one line, Python's.
  `NoargsGroup.main(None)` with `sys.argv` set to `['app', 'bogus']`: status 2 and the error on
  stderr, not the help. Every test that calls `main(None)` patches `sys.argv` to the program name
  alone (pytest's own argument list is otherwise what argparse reads). New tests are named
  `test_app_argument_error_*` (the report) or `test_app_group_*` (the bare group): the mutant
  sweep counts a kill only from those families.

### Requirement → design map

| R-ID | Design element(s) that satisfy it |
|------|-----------------------------------|
| R1   | `ArgumentError` branch of `Application.main`: `_hidden_by_null_handler` true (C6) and default `log_critical` → `print(error, file=sys.stderr)`; where no handler is found at all, Python's own line, and cmdkit's write is false (once, F1); status unchanged |
| R2   | a handler found on the chain, a rejecting filter, or the logger or last resort silenced → `_hidden_by_null_handler` false → no write; `log_critical` called as today, so configured handlers get the same one record |
| R3   | `cls.log_critical == log.critical` false → no write; the replacement called once, as today |
| R4   | `ApplicationGroup.main` maps an empty command line to `['--help']` under `ALLOW_NOARGS is True` when the group's interface rejects an empty command line; an optional `command` passes it on to `run` (C7) |
| R5   | the same condition false without the opt-in → `Application.main` unchanged; `Application` untouched |
| R6   | tests placed side by side as listed under Tests; `test_app_group_usage` unchanged; every decision of the report and the bare group pinned by a suite test, graded by the mutant sweep (F5) |
| R7   | decision computed per call by reading the handler chain; no handler added; import untouched |
| R8   | docstrings of `Application.main` and `ApplicationGroup.main`; `docs/api/app.rst` paragraphs |
| R9   | the § Invariants 3 bullet removed in P1, the phase that changes `Application.main` |

## 3. Invariant gate (AGENTS.md constitution check)

Checked against `AGENTS.md` § Invariants before research and again after this design was drafted.
The change touches `src/cmdkit/app.py`, on the high-blast-radius list; no other listed path.

- **§ 1 Compatibility.** The dropped message is an outright failure, fixed by default, as the GOAL
  says; no test pinned the silence. Configured logging and a replaced `log_critical` see no change
  (R2, R3), and neither does any setup that silences Python's last resort (C6), so the write
  appears only where Python itself would have printed the record without cmdkit's `NullHandler`,
  and never beside Python's own line (review F1). The bare group's help is an opt-in through an
  existing attribute whose only effect on a group that requires its command is a silent exit 2
  today; a group whose `command` is optional keeps calling `run` (C7, review F2), and without the
  opt-in a bare group is byte for byte 2.7.7's, each test beside the opt-in's. Every `ExitStatus` value is unchanged; no name leaves `__all__`.
- **§ 3 Command line.** `Interface` still never exits or prints. `main` still returns an
  `ExitStatus` int, never calls `sys.exit`, and re-raises what it doesn't handle. Help and usage
  text print as written. The recorded limitation is removed with its fix (R9, C5).
- **§ 4 Footprint.** No import-time effect is added: the decision reads the handler chain when an
  error is caught, and attaches nothing. Python 3.9 floor: the code uses nothing newer
  (bound-method equality and `Logger.isEnabledFor` honouring `disabled` both predate 3.9); the
  gates run on 3.9 and 3.14.
- **§ Conventions.** Docstrings and `docs/api/app.rst` change in the commit that changes the
  behaviour; no spec ids in source or tests; code style as `src/cmdkit/`.

### Deviation justifications

| Deviation | Why needed | Simpler alternative rejected because |
|-----------|-----------|--------------------------------------|
| **"No logging configured" is Python's last-resort rule (GOAL C6, ruled at the sign-off).** cmdkit writes exactly when `Logger.callHandlers` would hand this `CRITICAL` record to `logging.lastResort` were cmdkit's `NullHandler` not there: the logger enabled for `CRITICAL` (not disabled, not under `logging.disable`), `lastResort` present and at or below `CRITICAL`, and no handler found on the `propagate` chain, whatever its level. `dictConfig`'s default `disable_existing_loggers`, `logging.disable(CRITICAL)`, handlers levelled above `CRITICAL`, a `cmdkit.app` level above `CRITICAL` and `lastResort = None` stay silent, as in 2.7.7; `propagate = False` on `cmdkit` with no handler of the application's there prints, as Python would ([research/01](research/01-call-time-decision.md), probed). The `lastResort` presence and level test is the part of that same rule C6 doesn't spell out. Revised after review cycle 1: where the walk finds no handler at all, Python's last resort has printed the record, so cmdkit writes nothing (F1); a filter on `cmdkit.app` that rejects the record keeps it silent, as `Logger.handle` would (F3). Both are the same rule read to its end: the line appears exactly when cmdkit's `NullHandler` is the only reason Python did not print it. | C6 replaces the literal "would receive" reading of the definition above R1, which wrote the bare line in setups applications use to silence logging. | The literal reading (count only handlers whose level the record meets; write for a disabled logger) is what C6 overruled: it adds output for applications that silenced cmdkit, a changed default under § Invariants 1. Leaving out the `lastResort` test would write where Python, with `lastResort = None` or levelled above `CRITICAL`, prints nothing. |
| **The filter is asked about a record cmdkit builds (review F3).** The decision calls `cmdkit.app`'s `filter` with a record from `makeRecord` (`msg` the error, no arguments, no caller information) after `log_critical` has logged its own, so a logger filter sees two records per caught error where it saw one. | Python's own decision (`Logger.handle`) runs the filters on the record before `callHandlers`, and cmdkit has no hook inside that call without attaching something. | Reading the outcome of the real call needs a handler or a filter of cmdkit's on the logger for the duration of the call: the process-wide mutation [research/01](research/01-call-time-decision.md) rejected (option 2: other threads logging to `cmdkit` meet it). Calling the filter before `log_critical` instead changes only which of the two calls comes first. A filter that keeps state (a rate limit, a counter) can count the extra record; one that rejects only the second sees cmdkit stay silent. Both are filters the application wrote for its own records; § 5 records it. |
| **A bare group "would fail on the missing command" is read as: its interface rejects the bare command line (GOAL C7, review F2).** `ApplicationGroup.main` parses the given `cmdline` (`[]`, or `None`, read from `sys.argv` as 2.7.7 does under the opt-in) with the group's own interface and shows the help only when that raises `ArgumentError`. GOAL R4's parenthetical, that `main` already treats `None` as empty, holds without the opt-in only; with it, 2.7.7 parses `sys.argv`, and C7's "exactly as on 2.7.7" keeps that. | C7 names the missing command; the parse is how cmdkit asks argparse whether a bare run fails, without reading argparse's private action list or its message text. | Testing the `command` action's `required` flag reads a private attribute (`_actions`) whose meaning for `nargs='*'` changed across Python versions; matching the error message breaks under translation. The reading differs from C7's words only for a group whose `command` is optional but which requires another argument: it shows the help where C7 read literally would report that other argument's error and exit 2. No group in the docs, tests or known users is built so; a bare run there was an `ArgumentError` exiting 2 in silence on 2.7.7, so the opt-in still changes only a configuration that failed. Flagged for the sign-off. |
| **cmdkit's `NullHandler` is identified by exact type and place:** any `logging.NullHandler` (not a subclass) on the `cmdkit` logger is treated as cmdkit's. A `NullHandler` the application adds anywhere else, root included, counts as a configured handler and keeps cmdkit silent. | The GOAL names "the `NullHandler` cmdkit attaches at import". cmdkit keeps no reference to it, and a re-import of the package adds a second one. | Holding a reference in `__init__.py` and comparing by identity touches a second high-blast-radius path and would count a re-import's second `NullHandler` as the application's, silencing R1. The only setup the type test misreads is an application that adds its own plain `NullHandler` to the `cmdkit` logger and nothing else; it then sees the bare line. |

Each row read against R1, R2, R3 and R7 as C6 words them: row 1 is C6's own reading; it and the
last row keep R2 and R3 exact (any handler found on the chain suppresses the write, so configured
handlers get only their own record; any replacement suppresses it), and none attaches anything.
The last row still holds under C6, which names "cmdkit's own `NullHandler`" the same way. Row 2
(the filter's second record) keeps R1's "once": the extra record reaches no handler and writes
nothing; it changes what a stateful filter counts, not what is printed. Row 3 read against R4 and
R5 as C7 words them: a group that requires its command shows the help (R4), a group with an
optional command calls `run` (C7), and without the opt-in nothing changes (R5); the one shape where
the reading and C7's words part is named in the row.

## 4. Rabbit holes (resolved)

- **Deciding "unconfigured" without a lasting handler** → a call-time walk mirroring
  `Logger.callHandlers`'s last-resort decision (C6); a temporary handler, removing the `NullHandler`, and an identity reference
  were each rejected ([research/01](research/01-call-time-decision.md)).
- **pytest's root handlers** → four handlers on root in every phase; hiding them works only inside
  the test body, in place; a fixture or a list swap leaks or misses
  ([research/02](research/02-pytest-logging.md)).
- **Replacement detection** → bound-method equality, probed on 3.9; identity fails because each
  `log.critical` access builds a new bound method.
- **Research triggers.** Trigger 2 fired (`src/cmdkit/app.py` is on the high-blast-radius list):
  two focused briefs, scaled to the small appetite. Trigger 1 did not (the root cause is known and
  probed in the GOAL). Trigger 3 did not: the deliverables are a behaviour fix, an opt-in and
  tests that pin them, not a gate, a CI step or test infrastructure; the gate scripts in `verify/`
  are this cycle's own verification, mutation-tested in the dry run (§ 6), and the test-module
  context manager is a three-line fixture whose failure mode (handlers not hidden) shows red, not
  green. No adversarial reviewer ran.
- **Review cycle 1 (2026-11-11).** F1: the helper returned true when the walk found no handler,
  the very case where Python's last resort prints; the walk now counts cmdkit's handlers and
  returns false when it found none. F3: the logger's own filters are consulted on a built record
  (§ 3, row 2). F5: every decision is pinned in `tests/test_app.py`, and `verify/mutants.py`
  grades the suite alone against a mutant per decision. F2: the bare group's help needs a failing
  parse of `[]` (C7; § 3, row 3). **Trigger 3 fires for this revision**: F5's deliverable is the
  suite's assertions and the sweep that grades them, a verification harness, so one adversarial
  reviewer ran against the revised design, gates and prototype. It confirmed 5 findings and 1
  plausible, all folded: `main(None)` under the opt-in ignored `sys.argv` (the probe now parses
  `cmdline`); the probe record's message, level and name were unpinned (three filter setups, three
  mutants); a replacement compared by function only survived the suite (a test, a mutant); a test
  pinning the module's source would kill every mutant (kills count only from the pinning test
  families, and `change_set.py` refuses added test lines that read the source); a build commit
  with the plan's subject could re-freeze `verify/` (`frozen` checks every plan commit's files).
  Its setups the rule does not model are in § 5.

## 5. Risks & open questions

- **A replaced `lastResort` is not modelled.** An application that replaced `logging.lastResort`
  with a handler of its own gets cmdkit's bare line where Python, without cmdkit's `NullHandler`,
  would have handed the record to that handler. Rare, and not pinned by a gate. (Cycle 1 listed
  logger filters here too; review cycle 1 made them part of the rule, F3.)
- **A logger filter sees a second record** (§ 3, row 2): a stateful filter on `cmdkit.app` counts
  one more record per caught argument error, and one that rejects only the second keeps cmdkit
  silent. Not pinned by a gate.
- **Setups the rule does not model** (adversarial review, confirmed on 3.9 and 3.14, base silent
  in each): a filter on `cmdkit.app` that demotes the record's level (the helper compares the
  level it was given, not the filtered record's), a filter on `logging.lastResort` itself, and an
  application that sets `cmdkit`'s handlers to its own plain `NullHandler` to silence it (§ 3,
  last row): cmdkit prints the line in each. The reverse: a filter that passes each message once
  keeps cmdkit silent (§ 3, row 2). All need a filter or handler written to defeat the rule; none
  is pinned by a gate.
- **The plan subject is the freeze anchor.** `frozen` checks `verify/` against the latest
  `[fix] Plan cli-defaults:` commit and requires every such commit to touch only the plan's files,
  so a build commit carrying code can't re-freeze it; a spec-only commit with that subject still
  could. The review reads the branch's commit list.
- **Exact text is the mutant sweep's contract.** `verify/mutants.py` anchors on § 2's lines. A
  build that writes them differently gets a red "anchor found 0 times", never a green; the
  remedy is to write § 2's lines, or to stop and ask, never to edit `verify/`.
- **Sphinx is not in any gate.** The new `.. autoattribute:: ALLOW_NOARGS` under
  `ApplicationGroup` documents an inherited attribute; Read the Docs builds it after the merge. The
  review reads the rst; a local `sphinx-build` is optional.
- **The full suite still writes `/tmp/cmdkit/config`** until the open tests-to-`tmp_path` change
  lands, so the profile's `verify` needs `/tmp` writable (sandbox off). The phase gates run only
  `tests/test_app.py`, which writes nothing outside the temporary directory, and run sandboxed. No
  gate asserts anything about `/tmp/cmdkit`.
- **A pre-existing flaky test.** `test_app_invalid_options` draws random long options and expects
  an `ArgumentError`, but argparse takes `--he` as `--help`; on `develop` it fails about 1 run in
  40 per Python (measured over 40 seeds on 3.14), and once failed, Hypothesis's `.hypothesis/`
  database replays the failure on every later run in that checkout. The phase gates pass
  `--hypothesis-seed=0`, which does not hit it; the profile's `verify` and CI are unseeded and can
  go red by chance. Deferred, not fixed here (every existing test stays byte for byte):
  `issues/test-invalid-options-help-prefix.md`, with its `ROADMAP.md` entry, filed with this plan.
  A red `test_app_invalid_options` with `opt='he'` (or another prefix of `--help` or `--debug`;
  prefixes of `--option` raise `ArgumentError` and pass, review F4) at the push is this, and
  clearing `.hypothesis/` and re-running is the remedy.
- **Merge order with the sibling changes.** Neither touches `src/cmdkit/app.py`,
  `tests/test_app.py`, `docs/api/app.rst` or the § Invariants 3 bullet; a rebase onto either is
  textual-conflict free in `AGENTS.md` (checked against both branches).

## 6. Verification strategy

cmdkit is a library with no throwaway-environment helper, so the gates drive `main` directly, in
fresh child interpreters, alongside the profile's `verify` narrowed to `tests/test_app.py`. All of
it is in `verify/gate.sh` (POSIX `sh`), which installs an export of the git index, editable, into
a fresh isolated uv environment per Python (3.9 and 3.14), so it grades what the phase's commit
will hold:

- `verify/drive_main.py errors`: the R1 cases at the top level, inside a group's command, in a
  nested group, and an `ALLOW_NOARGS` application missing its positional (stderr exactly the
  message and a newline, stdout empty, status 2); `basicConfig` before import (one formatted line,
  nothing bare, also for an error inside a command); a handler on the `cmdkit` logger (one record);
  an application `NullHandler` on root (silent); `log_critical` replaced on the class, on
  `Application`, and by another logger's `critical` (Python's own one line, nothing from cmdkit);
  unconfigured → configured → unconfigured in one process (bare, formatted, bare); the
  `KeyboardInterrupt` path unchanged (status 4, silent); the C6 setups on both sides (silent:
  `dictConfig` after import with its default, `logging.disable(CRITICAL)`, a root handler levelled
  above `CRITICAL`, `cmdkit.app` levelled above `CRITICAL`, `lastResort = None`, `lastResort`
  levelled above `CRITICAL`; printing: `propagate = False` on `cmdkit` with root configured, and
  `cmdkit.app` and `lastResort` at `ERROR`; `dictConfig` keeping existing loggers: its own line
  only); and the handler lists of `cmdkit`,
  `cmdkit.app` and root after import and after reported errors equal 2.7.7's
  (`cmdkit: [NullHandler]`, the others empty, measured at `b9efaca`).
- `verify/drive_main.py noargs`: an `ALLOW_NOARGS` group's `main([])`, `main(None)` and `main()`,
  with `ALLOW_PARSE`, and nested as a command, each byte-equal to its `--help` run with status 0;
  without the opt-in, `main([])`, `main(None)` and the nested bare run print usage with status 1; a
  plain application with and without `ALLOW_NOARGS`.
- `verify/change_set.py`: only the cycle's files change; `AGENTS.md` loses exactly the one bullet;
  no spec ids in added source or test lines; every existing test in `tests/test_app.py` is
  unchanged (`test_app_group_usage` among them) and tests were added. P2 adds the `ALLOW_NOARGS`
  docs correction, that the `AGENTS.md` commit also changes `app.py`, and the deferral ledger.

**Revised after review cycle 1.** `verify/` is re-frozen at this revision's plan commit; the
gates keep every check above and add:

- `drive_main.py errors`, F1: for each of the 7 error targets, the three setups that leave no
  handler at all (`dictConfig` naming `cmdkit`, `cmdkit`'s handlers cleared, `propagate = False` on
  `cmdkit.app`) give exactly one line, the bare message: 21 checks. F3: a rejecting filter on
  `cmdkit.app` is silent, at the top level and for an error inside a group's command; an accepting
  one prints the bare line once; a rejecting filter on `cmdkit`, which Python does not consult,
  prints the bare line once; filters that select on the message (`silent`), the level
  (`CRITICAL` only: once) and the logger name (once).
- `drive_main.py noargs`, F2 (C7): an `ALLOW_NOARGS` group whose `command` is `nargs='?'` calls
  its `run` on `main([])`, `main(None)` and `main()` and nested bare as another group's command
  (`default action`, status 0); it still runs a named command; without the opt-in it prints usage
  with status 1. The groups that require their command keep their help checks unchanged, and
  `main(None)` with `sys.argv` `['app', 'bogus']` reports the error (status 2) and with
  `['app', 'cmd']` dispatches as 2.7.7 does (the command's usage, status 1).
- `mutants.py P1|P2` (gate mode `mutants P1|P2`, in the phase gates), F5: an exact-text mutant
  per decision, applied to the export's `src/cmdkit/app.py`, with `tests/test_app.py` alone run
  against each under a fresh bytecode prefix; each must fail the suite (pytest exit 1) with at
  least one failing test from its family (`test_app_argument_error_*` or
  `test_app_noargs_allowed_*` for the report, `test_app_group_*` for the bare group), and the
  file must come back byte for byte. A missing anchor, a survivor, a kill from outside the family
  or a broken mutant is red. P1's 21: the enabled check removed, or reduced to
  `logger.disabled`; the probe record built with no message, at `DEBUG`, or named `cmdkit`; the
  filter check removed; the
  `lastResort` presence check removed, its level check removed, or its boundary moved to `<=`;
  the `propagate` stop removed; handler levels counted; any `NullHandler` anywhere, a subclass,
  or one on `cmdkit.app` counted as cmdkit's; cmdkit's own counted as the application's; true
  returned when no handler is found (F1's bug) or false when only cmdkit's is; the replacement
  check removed, or reduced to comparing the function; the level argument changed to `WARNING`;
  the write sent to stdout. P2 adds 4: the parse check removed, help shown when the parse
  succeeds, `[]` parsed in place of `cmdline`, the opt-in ignored.
- `change_set.py`: no added test line reads the module's source or bytecode (`inspect`,
  `__file__`, `hashlib`, `co_code`, `linecache`, `__code__`).
- `gate.sh` grades the change set from the cycle's *first* plan commit, the tree the build
  started from (it was the latest plan commit, which this revision moves past the build's
  commits); `frozen` checks `verify/` against the latest plan commit, and that every plan commit
  touches only `spec/cli-defaults/`, `issues/` and `ROADMAP.md`.

**Dry run** on a detached prototype at `origin/develop` (`b9efaca`), cut to each phase's tree,
after the C6 revision (the record of the first plan):

- P1 tree (fix, P1 tests, `log_critical` docs, the `AGENTS.md` bullet): `gate.sh P1` green on 3.9
  and 3.14 in about 5 s warm (38 tests); `drive_main.py noargs` red on it (5 opt-in checks), as it
  should be before P2. On `b9efaca` itself, `errors` is red on the 7 unconfigured cases, the
  per-call case, and the two C6 printing cases, and green on the checks that keep 2.7.7's
  behaviour, the six C6 silent setups among them.
- Mutants, each staged on its phase's tree and each killed: no write; an unconditional write;
  replacement ignored; handlers ignored; handlers counted only when their level admits the record
  (the overruled reading); the enabled check removed; `logger.disabled` alone in place of
  `isEnabledFor`; the `lastResort` test removed; `propagate` ignored; the level argument changed to
  `WARNING`; every `NullHandler` excluded; cmdkit's `NullHandler` counted; the write to stdout; a
  prefixed message; `sys.stderr` bound at import (killed by the in-process tests only, which is
  why the gate runs both); a stderr handler left attached; an extra `AGENTS.md` edit;
  `test_app_group_usage` edited; a spec id in a source line.
- P2 tree (everything): `gate.sh P2` green on 3.9 and 3.14, about 6 s warm (43 tests in
  `tests/test_app.py`). P2 mutants, each killed (P2's code is unchanged by C6): the opt-in ignored
  (every bare group shows help); usage printed instead of help; help printed with status 1; the
  docs' bare-run status left at `exit_status.success`; an unseeded deferral line in a phase body.
- Full suite, once, with the profile's `verify` on the P2 tree (sandbox off for `/tmp/cmdkit`):
  89 passed and 1 failed on each of 3.9 and 3.14 in the prototype checkout, the failure being the
  pre-existing `test_app_invalid_options` flake above, replayed from that checkout's
  `.hypothesis/` (`opt='he'`, reproduced on `b9efaca` with the same example); from a fresh export
  of the same tree with `--hypothesis-seed=0`, 90 passed on each.
- Where the dry run stops: the gates name no test or mutant build writes, so they ran end to end
  on the prototype; only `frozen` was skipped (no plan commit there), and the change set was graded
  from `b9efaca` in place of the plan commit (`CLI_DEFAULTS_GATE_DRYRUN`, never set by a build).

**Dry run after review cycle 1** (2026-11-11), with the adversarial review folded, on a detached
prototype at the branch head (`3eaed23`, the maintainer's rulings) and on a throwaway clone of it
carrying this revision as a `[fix] Plan cli-defaults:` commit, so `frozen` and the
first-plan-commit base ran for real:

- **Unremediated head, the new checks red:** `errors` fails 24 checks (the 21 F1 checks, 3
  setups × 7 targets, each printing two lines; 3 F3 checks, the rejecting and the
  message-selecting filters, each printing one) and passes the rest; `noargs` fails 6 (the 4 F2
  optional-command checks print the help in place of `default action`, and the 2 `sys.argv`
  checks print the help); `mutants P2` is red: 17 anchors missing, 3 mutants killed (the enabled
  check twice, the write to stdout), and 5 survive the cycle-1 suite (the `lastResort` presence,
  level and boundary, the `propagate` stop, handler levels): the F5 survivors. The revised suite
  run against the unremediated `app.py` fails on the no-handler setups (F1), the rejecting filter
  (F3) and the optional command (F2).
- **P1's tree** (the helper, its call site, docstring and docs, P1's tests; `ApplicationGroup.main`
  as cycle 1 left it): `gate.sh P1` green on 3.9 and 3.14, `frozen` included, 68 tests,
  `mutants P1` 21 of 21 killed on each; `noargs` red on it (the 6 checks above), as it should be
  before P2.
- **P2's tree** (everything): `gate.sh P2` green on 3.9 and 3.14, 71 s warm; `tests/test_app.py`
  71 passed; `mutants P2` 25 of 25 killed on each, every kill from its family.
- **The guards:** a test added to the suite that hashes `inspect.getsource(cmdkit.app)` turns
  `static P2` red.
- **Full suite once** on P2's tree, with the profile's `verify` (sandbox off, `--hypothesis-seed=0`):
  118 passed on each of 3.9 and 3.14.
- Where it stops: the gates name no test build writes beyond § 2's lines and the test families,
  so they ran end to end.
