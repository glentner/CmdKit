---
status: unshaped
kind: fix
appetite: small
---

# The argument-error report follows `Logger.handle` when filters keep state or read caller fields

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

With no logging configured, `Application.main` writes an argument error's message to stderr when
cmdkit's own `NullHandler` is the only reason Python's last-resort handler did not print the record
(`_hidden_by_null_handler` in `src/cmdkit/app.py`). It decides by following `Logger.handle` and
`Logger.callHandlers`, but in two places it does not see what Python saw:

- **The filter check runs on a record cmdkit builds,** after `log_critical` has logged the real one.
  The built record has no caller information (`funcName`, `lineno`, `pathname`), so a logger filter
  on `cmdkit.app` that selects on those fields can decide differently. A filter that keeps state (a
  once-per-message filter, a rate limit, a counter) sees two records per error: it can let the real
  record through and reject the second, so cmdkit stays silent where Python, without the
  `NullHandler`, would print; or count one record too many. A filter that changes the record's
  level, or (3.12+) returns a replacement, is not followed either: the helper compares the level it
  was given.
- **`logging.lastResort`'s own filters are not consulted.** `lastResort.handle` would drop a record
  its filters reject; cmdkit prints it.

All of these need a filter written for the application's own records; no default setup reaches
them.

## Why it was deferred

Found by the `cli-defaults` cycle's second review (rated low), deferred by the maintainer so the
report could ship. Reading the outcome of the real call needs a hook inside it, which the cycle
ruled out (no handler or filter attached, even for the call's duration).

## Outcome / vision

cmdkit writes the line exactly when Python, without cmdkit's `NullHandler`, would have printed this
record, filters included, and asks each filter about the record once.

## Sketch of the acceptance criteria

- **R1** — A stateful filter on `cmdkit.app` SHALL see one record per caught argument error.
- **R2** — A filter on `cmdkit.app` that selects on caller fields, or lowers the record's level,
  SHALL lead to the same outcome Python's last resort would give.
- **R3** — A filter on `logging.lastResort` that rejects the record SHALL keep cmdkit silent.

## Tests that would show it

- A once-per-message filter on `cmdkit.app`, logging unconfigured: `Group.main(['bogus'])` prints
  the message once (today: nothing), and the filter's counter reads one.
- A filter on `cmdkit.app` that sets `record.levelno = logging.INFO` with `lastResort` at `WARNING`:
  nothing printed (today: the line).
- A filter on `logging.lastResort` that rejects every record: nothing printed (today: the line).
- Each compared with the same setup with cmdkit's `NullHandler` removed, run on Python 3.9 and the
  newest supported Python.

## Notes

- Related: `issues/group-noargs-help.md` (the same cycle's other deferral).
- Found by: the `cli-defaults` cycle, second review.
