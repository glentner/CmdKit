---
status: unshaped
kind: fix
appetite: small
---

# A group's own exception handlers never swallow its command's exit status

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

- **The handler table is shared.** `Application.exceptions` (`src/cmdkit/app.py:62`) is one `dict` on
  the base class. Every subclass that doesn't define its own shares it (probe:
  `Application.exceptions is SubApp.exceptions` is `True`), so `SubApp.exceptions[E] = handler`
  registers `handler` for every application in the process.
- **A group can lose its command's status.** `ApplicationGroup` returns a command's exit status by
  raising `CompletedCommand` from `run`, which is handled by its own `exceptions` entry
  (`app.py:168-170`, `:190-197`). A group subclass that defines `exceptions = {...}` without that
  entry loses the status: `CompletedCommand` falls through to "uncaught exception occurred!" and
  `main` re-raises it.

## Why it was deferred

Pre-existing on `develop`. Found while evaluating cmdkit for a command-line tool (the shared table)
and by the adoption sweep (the group).

## Outcome / vision

- **By default** (an outright failure): `ApplicationGroup.main` handles `CompletedCommand` itself,
  whatever the subclass's `exceptions` holds.
- **The shared table:** isolating each class's table changes what
  `Application.exceptions[E] = h` does today (it applies to every application), so isolation is a
  default change. Decided at adoption: isolation is an explicit opt-in, and the shared table stays
  the default (documented).

## Sketch of the acceptance criteria

- **R1** — WHEN a group subclass defines its own `exceptions` without a `CompletedCommand` entry,
  `main` SHALL return its command's exit status and log no uncaught exception.
- **R2** — By default, a handler registered on `Application.exceptions` SHALL still apply to every
  application, with a test pinning it.
- **R3** — WHERE an application class opts in to its own table, a handler registered on it SHALL NOT
  apply to any other class, and a handler registered on another class SHALL NOT apply to it.

**Test that shows it:** a group subclass with `exceptions = {ValueError: lambda e: 9}` and a command
whose `run` returns normally: `Group.main(['cmd'])` returns 0, with nothing logged at error or
critical level. A command whose handler maps its exception to 3: `Group.main([...])` returns 3.

## Notes

- HyperShell defines `exceptions = {…}` on its own application classes, building fresh tables, so it
  isn't relying on the sharing.
- Waits on `cli-defaults` and `cli-command-suggestions` (`app.py`).
- Found by: an evaluation of cmdkit 2.7.7 for a command-line tool, 2026-11, and the adoption sweep,
  2026-11-10.
