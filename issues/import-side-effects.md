---
status: unshaped
kind: fix
appetite: small
---

# Importing cmdkit leaves other parsers' `--version` alone

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

Importing cmdkit changes the whole process:

- **`argparse`'s version action.** `src/cmdkit/cli.py:45-47` replaces
  `argparse._VersionAction.__call__` for every parser in the process. After `import cmdkit`, a plain
  `argparse.ArgumentParser` in any other library raises `cmdkit.cli.VersionOption` on `--version`,
  instead of printing the version and exiting. Probe on `develop` under 3.14: a plain parser
  created *before* the import raises `VersionOption: 1.0`.
- **Logging.** `src/cmdkit/logging.py:50-59` registers the `NOTICE`, `TRACE` and `DEVEL` level names.
  `:143` installs `cmdkit.logging.Logger` as the logger class, and `:210` installs `LogRecord` as the
  record factory, for every library in the process.

## Why it was deferred

Pre-existing on `develop`. Found while evaluating cmdkit for a command-line tool.

## Outcome / vision

- **By default** (it breaks other code outright): the `--version` override is scoped to `Interface`,
  registered as the parser's own `version` action, so a plain `argparse` parser behaves as the
  standard library documents. `Interface` still raises `VersionOption`.
- **Recorded, not changed:** the logger class, the record factory and the level names stay.
  Consumers call `.notice()` and `.trace()` on loggers from `logging.getLogger`, and removing those
  would change a default. The factory's one outright failure, discarding a factory installed before
  cmdkit, is `issues/logging-record-factory.md`.

## Sketch of the acceptance criteria

- **R1** — WHEN cmdkit has been imported, a plain `argparse.ArgumentParser` with a `version` action
  SHALL print the version and raise `SystemExit(0)` on `--version`.
- **R2** — An `Interface` with a `version` action SHALL still raise `VersionOption` carrying the version.
- **R3** — `argparse._VersionAction.__call__` SHALL be the standard library's after the import.

**Test that shows it:** in a subprocess (a clean interpreter), import cmdkit, build a plain parser
with `action='version', version='1.0'`, and parse `['--version']`: it exits 0 and prints `1.0`. In the
same process, `Interface` raises `VersionOption('1.0')`. The existing version tests in
`tests/test_app.py` pass unchanged.

## Notes

- `argparse-help-fallback` edits `cli.py` after this and has to meet the same action.
- `AGENTS.md` § Invariants 4 lists the import-time effects; this shrinks the list.
- Found by: an evaluation of cmdkit 2.7.7 for a command-line tool, 2026-11.
