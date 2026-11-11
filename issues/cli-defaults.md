---
status: adopted:cli-defaults
kind: fix
appetite: small
---

# Argument errors reach stderr, and a group can show its help when run bare

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

- **Error messages are dropped.** `Application.main` reports an `ArgumentError` through
  `log_critical`, which defaults to the `cmdkit.app` logger's `critical` (`src/cmdkit/app.py:63`,
  `:125-127`). `cmdkit/__init__.py:33` gives the `cmdkit` logger a `NullHandler`, so Python's
  last-resort stderr handler never fires. With no logging configured, every argument error is
  silent: an unknown option exits 2 with nothing printed, and so does an unknown command in a group.
  Probe on `develop`: `Group.main(['bogus'])` returns `(2, stdout '', stderr '')`.
- **A bare group can't show its help.** A bare `ApplicationGroup` prints its usage and exits 1
  (`app.py:103-108`). Setting `ALLOW_NOARGS = True` on a group doesn't help: the `command` positional
  is required, so it exits 2, silently (see above).

## Why it was deferred

Pre-existing on `develop`. Found while evaluating cmdkit for a command-line tool; a second tool hit
the silent exit on an unknown flag.

## Outcome / vision

- **By default** (dropped messages are an outright failure): when the application hasn't overridden
  `log_critical` and no handler other than cmdkit's `NullHandler` would receive the record, the
  message is written to stderr. A consumer's override still wins (HyperShell assigns
  `Application.log_critical`), and a configured handler gets the message exactly once.
- **Opt-in:** `ALLOW_NOARGS = True` on a group prints the group's help and exits 0 when run bare.
  Today that setting yields a silent exit 2, so giving it a meaning breaks nobody.
- **Unchanged:** a bare group without the opt-in still prints usage and exits 1;
  `tests/test_app.py::test_app_group_usage` pins it.

## Sketch of the acceptance criteria

- **R1** — WHEN `main` catches an `ArgumentError` and no logging is configured, the message SHALL
  appear on stderr and `main` SHALL return `exit_status.bad_argument`.
- **R2** — WHEN the application overrides `log_critical` or a handler is configured, the message
  SHALL go there, once, and not also to stderr.
- **R3** — WHEN a group with `ALLOW_NOARGS = True` runs with no arguments, it SHALL print its help to
  stdout and return `exit_status.success`.
- **R4** — WHEN a group without it runs bare, it SHALL behave as 2.7.7 does.

**Test that shows it:** in a fresh interpreter with logging unconfigured, `Group.main(['bogus'])`
returns 2 and stderr contains `bogus`. With `logging.basicConfig` and `caplog`, the message is
logged once and stderr is empty. A group with `ALLOW_NOARGS = True`: `main([])` returns 0 and prints
its help text.

## Notes

- `Application.main(cmdline=None)` treats `None` as an empty command line (`if not cmdline`,
  `app.py:103`) and never reads `sys.argv`. The documented call is `main(sys.argv[1:])`, so this is
  left alone. Reading `sys.argv` by default would be a default change.
- Should the message carry the program name, as argparse's `prog: error: …` does? Decide at shaping.
- `cli-command-suggestions` and `app-exception-handlers` edit `app.py` after this.
- Found by: an evaluation of cmdkit 2.7.7 for a command-line tool, 2026-11.
