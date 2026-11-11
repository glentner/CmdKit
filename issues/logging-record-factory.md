---
status: unshaped
kind: fix
appetite: small
---

# cmdkit's log record factory wraps the one already installed, with a test for #20

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

Issue #20: after `import cmdkit`, `logging.makeLogRecord({'foo': 'bar'})` raised `AttributeError`,
because `cmdkit.logging.LogRecord.__init__` split a `name` that `makeLogRecord` passes as `None`. The
2.7.2 fix still holds on `develop` (`src/cmdkit/logging.py:180-184` guards a non-string name; probe
under 3.9 and 3.14: the call returns a record with `foo == 'bar'`). But no test covers it, and
`tests/` has no logging tests at all.

The issue's discussion left a second problem open. `logging.setLogRecordFactory(LogRecord)`
(`logging.py:210`) *replaces* the factory, so any factory installed before cmdkit is imported is
discarded. The standard library documents exactly that pattern: a function that calls the previous
factory and adds attributes. A library that used it loses its attributes on every record once cmdkit
is imported.

## Why it was deferred

The first problem was fixed without a test in 2.7.2. The second was noted on #20 ("this is worth
looking into") and never done.

## Outcome / vision

A regression test for #20. cmdkit's factory wraps whatever factory is in place when cmdkit is
imported: it calls it, then adds cmdkit's attributes. Earlier factories keep working, which is an
outright failure fixed by default. `LogRecord` stays exported, and records keep every attribute the
logging styles use.

## Sketch of the acceptance criteria

- **R1** — WHEN cmdkit has been imported, `logging.makeLogRecord({'foo': 'bar'})` SHALL return a
  record with `foo == 'bar'`.
- **R2** — WHEN a factory was installed before cmdkit was imported, records SHALL carry both that
  factory's attributes and cmdkit's (`hostname`, `app_id`, `ansi_level`, `elapsed_hms` …).
- **R3** — Every format in `logging_styles` SHALL render a record without error.

**Test that shows it:** in a subprocess, install a function factory that sets `record.custom = 1`,
then import cmdkit. `logging.getLogger('x').makeRecord(…)` has `custom == 1` and a `hostname`, and
`makeLogRecord({'foo': 'bar'})` works. Then, for each style in `logging_styles`, a `Formatter` formats
a record.

## Notes

- `AGENTS.md` § Invariants 4 lists the record factory as an import-time effect; wrapping keeps it
  there without widening it.
- Related: #20 (closed, fixed in 2.7.2); `issues/import-side-effects.md`.
- Found by: adoption sweep, 2026-11-10, rechecking closed issues.
