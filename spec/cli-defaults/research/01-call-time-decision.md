# 01 — Deciding "no logging configured" at call time

**Question.** How does `Application.main` decide, when it catches an `ArgumentError`, whether to
write the message to stderr itself, without attaching a handler that outlives the call (GOAL R1,
R2, R3, R7; C1, C2)?

## What the code does today (`develop`, `b9efaca`)

- `Application.log_critical` is a class attribute holding the bound method `log.critical` of the
  module logger `cmdkit.app` (`src/cmdkit/app.py:63`). A bound method stored on a class is
  returned as is by `cls.log_critical` (probe: `Application.log_critical is
  Application.__dict__['log_critical']` is `True` on 3.9). `log.critical` builds a new bound
  method on each access, so `is` against a fresh `log.critical` is `False`, but `==` is `True`:
  bound methods compare equal when `__func__` is the same and `__self__` is the same object.
- `cmdkit/__init__.py:33` adds one `logging.NullHandler` to the `cmdkit` logger at import. After
  `import cmdkit` in a fresh interpreter the handlers are: `cmdkit` → `[NullHandler]`,
  `cmdkit.app` → `[]`, root → `[]` (probe, 3.9 and 3.14).
- `Logger.callHandlers` walks the logger and its ancestors while `propagate` holds, calls
  `handle` on each handler whose level the record meets, and fires `logging.lastResort` only when
  it found no handler at all. The `NullHandler` counts as found, which is why nothing is printed.

## Options for the decision

1. **Inspect the handler chain at call time** (chosen). In the `ArgumentError` branch, after
   calling `cls.log_critical(error)` as today: if `cls.log_critical == log.critical` (not
   replaced, C2) and no handler would receive a `CRITICAL` record from `cmdkit.app`, write
   `str(error)` and a newline to `sys.stderr` (looked up at call time). "Would receive" mirrors
   `callHandlers`: the logger must be enabled for `CRITICAL` (`isEnabledFor`, which also covers
   `logger.disabled` and `logging.disable`), then walk the chain while `propagate`, counting each
   handler whose level is at most `CRITICAL`, except a `logging.NullHandler` (exact type) on the
   `cmdkit` logger itself. Nothing is attached, so R7 holds by construction.
2. **Temporarily attach a stderr handler** around the log call and remove it after. Rejected:
   it is a process-wide mutation during the call (other threads logging to `cmdkit` would see
   it), it needs its own formatter to print the bare message, and it still needs the same "is
   anything configured" test to avoid duplicating a configured handler's line.
3. **Remove the `NullHandler`** so Python's last resort fires. Rejected: changes the import-time
   footprint (§ Invariants 4, R7) and prints only at `WARNING`+ through `lastResort`'s rules,
   which is the library-logging guidance cmdkit follows on purpose.
4. **Keep a reference to cmdkit's own `NullHandler`** (in `__init__.py`) and exclude it by
   identity. Rejected: touches `__init__.py`, a further high-blast-radius path, and a reload of
   the package (or a second import path) adds a second `NullHandler` that identity would then
   count as foreign and go silent. The exact-type test on the `cmdkit` logger covers both.

## Probed edge cases (prototype, 3.12; status 2 in every case)

| Setup before `main(['bogus'])` | develop stderr | design stderr |
|---|---|---|
| none | empty | `unrecognized command: bogus` |
| `logging.basicConfig(...)` | one formatted line | the same line, nothing else |
| `dictConfig`, `disable_existing_loggers` left `True` (cmdkit imported first) | empty | bare line |
| `dictConfig`, `disable_existing_loggers=False` | one formatted line | the same line |
| `logging.disable(logging.CRITICAL)` | empty | bare line |
| root handler at level 100 | empty | bare line |
| `cmdkit` logger `propagate = False`, root configured | empty | bare line |
| `NullHandler` on root, added by the application | empty | empty |

The four "bare line" rows below the first follow from GOAL's definition of "no logging configured"
(no handler other than cmdkit's `NullHandler` *would receive* the record): in each, none would. They
differ from what Python's own last-resort rule would do (it prints nothing for a disabled logger
and counts a handler whatever its level). PLAN records this as a reading for sign-off.

## Replacement detection (R3, C2)

`cls.log_critical == log.critical` is `False` for a function or `staticmethod` on the class, for a
function assigned to `Application.log_critical` (what one known consumer does), and for another
logger's `critical`. In the last case Python's own last resort may print once, if that logger has
no handler; that line is Python's, and cmdkit adds nothing (probe: stderr holds exactly one line).
