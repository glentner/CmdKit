# PLAN — Argument errors reach stderr, and a group can show its help when run bare

> **Status:** Draft for review · **Last updated:** 2026-11-11
> **Authoritative technical design.** The *how*. Vision/contract is [`GOAL.md`](GOAL.md);
> the phased executable roadmap is [`TECH.md`](TECH.md). Backing detail is in
> [`research/`](research/). Every design element traces to a GOAL R-ID.

## 1. Summary

Two small changes to `src/cmdkit/app.py`. In `Application.main`'s `ArgumentError` branch, after
calling `log_critical` as today, cmdkit writes the bare message to `sys.stderr` when
`log_critical` is still the default and Python's own last-resort handler would have printed the
record were cmdkit's `NullHandler` not there (GOAL C6); the decision is a walk of the handler chain
at the moment of the error, and nothing is attached. And
`ApplicationGroup` gains a `main` that turns an empty command line into `['--help']` when the group
sets `ALLOW_NOARGS = True`, so a bare group prints exactly its `--help` output and returns 0. Two
phases, one per behaviour, each with its tests and docs; the `AGENTS.md` line goes with the first.

## 2. Design

### Argument errors (`src/cmdkit/app.py`, `Application.main`)

The `except ArgumentError` branch becomes:

```python
except ArgumentError as error:
    cls.log_critical(error)
    if cls.log_critical == log.critical and _last_resort_would_print(log, logging.CRITICAL):
        print(error, file=sys.stderr)
    return exit_status.bad_argument
```

- **Replacement test (R3, C2).** `cls.log_critical == log.critical` holds only while the class
  resolves `log_critical` to the default, the `critical` bound method of the `cmdkit.app` logger
  (bound methods compare equal on the same function and the same logger object). A function or
  `staticmethod` on the class, a function assigned to `Application.log_critical`, or another
  logger's `critical` all compare unequal, and then cmdkit writes nothing, whether or not a handler
  stands behind the replacement.
- **Last-resort test (R1, R2; C6), a new private module function**
  `_last_resort_would_print(logger, level) -> bool`, following `Logger.callHandlers`'s last-resort
  decision with cmdkit's `NullHandler` taken out:
  1. `False` if `not logger.isEnabledFor(level)`: that covers `logging.disable`, a logger level
     above `level`, and `logger.disabled` (what `dictConfig` sets on loggers it disables); Python
     never builds the record then.
  2. `False` if `logging.lastResort` is `None` or its level is above `level`: Python would not
     print through it either.
  3. Walk `logger` and its ancestors while `propagate` holds; return `False` at the first handler
     found, whatever its level, except one whose exact type is `logging.NullHandler` on the logger
     named `cmdkit`. Return `True` when the walk finds none.

  So an application that silenced cmdkit (`dictConfig`'s default, `logging.disable`, handlers
  levelled above `CRITICAL`, `lastResort = None`) stays silent, and `propagate = False` on `cmdkit`
  with no handler of the application's there prints, as Python would.
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
        cmdline = ['--help', ]
    return super(ApplicationGroup, cls).main(cmdline, shared=shared)
```

`main([])`, `main(None)` and `main()` then follow `main(['--help'])` exactly: `from_cmdline`
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
  empty; the remaining C6 setups are pinned by the gate's fresh-interpreter drive.
- R7: the handler lists of `cmdkit`, `cmdkit.app` and root are the same before and after a call
  that reports on stderr.
- R4 beside R5: an `ALLOW_NOARGS` group's `main([])` and `main(None)` print what its
  `main(['--help'])` prints and return 0, placed after `test_app_group_usage`, which stays
  byte for byte; `Group.main(None)` prints usage and returns 1.
- R5, plain application: `ALLOW_NOARGS` with no required argument runs and returns 0; with a
  required positional, the bare run is an `ArgumentError`, reported on stderr per R1.

### Requirement → design map

| R-ID | Design element(s) that satisfy it |
|------|-----------------------------------|
| R1   | `ArgumentError` branch of `Application.main`: `_last_resort_would_print` true (C6) and default `log_critical` → `print(error, file=sys.stderr)`; status unchanged |
| R2   | a handler found on the chain, or the logger or last resort silenced → `_last_resort_would_print` false → no write; `log_critical` called as today, so configured handlers get the same one record |
| R3   | `cls.log_critical == log.critical` false → no write; the replacement called once, as today |
| R4   | `ApplicationGroup.main` maps an empty command line to `['--help']` under `ALLOW_NOARGS is True` |
| R5   | the same condition false without the opt-in → `Application.main` unchanged; `Application` untouched |
| R6   | tests placed side by side as listed under Tests; `test_app_group_usage` unchanged |
| R7   | decision computed per call by reading the handler chain; no handler added; import untouched |
| R8   | docstrings of `Application.main` and `ApplicationGroup.main`; `docs/api/app.rst` paragraphs |
| R9   | the § Invariants 3 bullet removed in P1, the phase that changes `Application.main` |

## 3. Invariant gate (AGENTS.md constitution check)

Checked against `AGENTS.md` § Invariants before research and again after this design was drafted.
The change touches `src/cmdkit/app.py`, on the high-blast-radius list; no other listed path.

- **§ 1 Compatibility.** The dropped message is an outright failure, fixed by default, as the GOAL
  says; no test pinned the silence. Configured logging and a replaced `log_critical` see no change
  (R2, R3), and neither does any setup that silences Python's last resort (C6), so the write
  appears only where Python itself would have printed the record without cmdkit's `NullHandler`. The bare group's help is an opt-in through an existing attribute whose only effect on a
  group today is a silent exit 2; without it a bare group is byte for byte 2.7.7's, and its test
  sits beside the opt-in's. Every `ExitStatus` value is unchanged; no name leaves `__all__`.
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
| **"No logging configured" is Python's last-resort rule (GOAL C6, ruled at the sign-off).** cmdkit writes exactly when `Logger.callHandlers` would hand this `CRITICAL` record to `logging.lastResort` were cmdkit's `NullHandler` not there: the logger enabled for `CRITICAL` (not disabled, not under `logging.disable`), `lastResort` present and at or below `CRITICAL`, and no handler found on the `propagate` chain, whatever its level. `dictConfig`'s default `disable_existing_loggers`, `logging.disable(CRITICAL)`, handlers levelled above `CRITICAL`, a `cmdkit.app` level above `CRITICAL` and `lastResort = None` stay silent, as in 2.7.7; `propagate = False` on `cmdkit` with no handler of the application's there prints, as Python would ([research/01](research/01-call-time-decision.md), probed). The `lastResort` presence and level test is the part of that same rule C6 doesn't spell out. | C6 replaces the literal "would receive" reading of the definition above R1, which wrote the bare line in setups applications use to silence logging. | The literal reading (count only handlers whose level the record meets; write for a disabled logger) is what C6 overruled: it adds output for applications that silenced cmdkit, a changed default under § Invariants 1. Leaving out the `lastResort` test would write where Python, with `lastResort = None` or levelled above `CRITICAL`, prints nothing. |
| **cmdkit's `NullHandler` is identified by exact type and place:** any `logging.NullHandler` (not a subclass) on the `cmdkit` logger is treated as cmdkit's. A `NullHandler` the application adds anywhere else, root included, counts as a configured handler and keeps cmdkit silent. | The GOAL names "the `NullHandler` cmdkit attaches at import". cmdkit keeps no reference to it, and a re-import of the package adds a second one. | Holding a reference in `__init__.py` and comparing by identity touches a second high-blast-radius path and would count a re-import's second `NullHandler` as the application's, silencing R1. The only setup the type test misreads is an application that adds its own plain `NullHandler` to the `cmdkit` logger and nothing else; it then sees the bare line. |

Each row read against R1, R2, R3 and R7 as C6 words them: row 1 is C6's own reading; both keep R2
and R3 exact (any handler found on the chain suppresses the write, so configured handlers get only
their own record; any replacement suppresses it), and neither attaches anything. Row 2 still
holds under C6, which names "cmdkit's own `NullHandler`" the same way.

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

## 5. Risks & open questions

- **Filters and a replaced `lastResort` are not modelled.** A filter on the `cmdkit.app` logger
  that rejects the record (Python then prints nothing) is not consulted, and an application that
  replaced `logging.lastResort` with a handler of its own gets cmdkit's bare line rather than that
  handler's output. Both are rare; reading a logger filter needs a built record, more than this
  appetite carries. Neither is pinned by a gate.
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
  A red `test_app_invalid_options` with `opt='he'` (or another prefix of a long option) at the
  push is this, and clearing `.hypothesis/` and re-running is the remedy.
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

**Dry run** on a detached prototype at `origin/develop` (`b9efaca`), cut to each phase's tree,
after the C6 revision:

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
