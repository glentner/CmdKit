---
status: unshaped
kind: feature
appetite: small
---

# An unknown command suggests the closest ones

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

An unknown command in an `ApplicationGroup` raises `ArgumentError(f'unrecognized command:
{self.command}')` (`src/cmdkit/app.py:252-253`). The message names no alternative, so a typo
(`confg`) leaves the user guessing. Python 3.14's argparse can suggest close matches
(`suggest_on_error`), but only for `choices`, and only on 3.14. A group dispatches a free positional
in `run`, so the feature never applies.

## Why it was deferred

A low-hanging feature found by the adoption sweep.

## Outcome / vision

On every supported Python, the error for an unknown command names the closest registered commands:
`unrecognized command: 'confg' (did you mean 'config'?)`. The exit status is unchanged, and so is
the message when nothing is close.

## Sketch of the acceptance criteria

- **R1** — WHEN a group receives an unknown command and one or more registered commands are close to
  it, the `ArgumentError` message SHALL name them.
- **R2** — WHEN none is close, the message SHALL be the 2.7.7 message.
- **R3** — The exit status SHALL stay `exit_status.bad_argument`.

**Test that shows it:** a group with commands `config` and `run`. `main(['confg'])` returns 2, and the
reported message contains `config`. `main(['zzz'])` reports `unrecognized command: zzz` exactly.

## Notes

- `difflib.get_close_matches` over the group's `commands` keys works on 3.9.
- Waited on `cli-defaults`, which made the message visible; it landed in #33.
- Found by: adoption sweep, 2026-11-10.
