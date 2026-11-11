# 03 — Marking cmdkit's own `NullHandler` (review cycle 2, F3; GOAL C9)

Trigger 2 fired again: the fix touches `src/cmdkit/__init__.py`, on the high-blast-radius list. One
focused probe, scaled to the small appetite, run by the planner on Python 3.9 and 3.14 against the
prototype and against `b9efaca`.

## Question

How does `_hidden_by_null_handler` tell the `NullHandler` cmdkit attaches at import from a
`NullHandler` the application puts on the `cmdkit` logger, without a new process-wide effect
(§ Invariants 4, R7)?

## Options

1. **An attribute on the existing handler** (`_null_handler._cmdkit_library_handler = True`,
   then `del _null_handler`). Chosen. The handler, its type, its logger and its place in
   `logging`'s shutdown list are those of 2.7.7; the module gains no name (the probe lists no
   `_null*` name in `vars(cmdkit)`); nothing enters `logging._handlers` (the handler is unnamed, as
   in 2.7.7).
2. **`Handler.set_name('cmdkit')`** and a name test. Rejected: `set_name` registers the handler in
   `logging._handlers`, a process-wide registry `dictConfig` reads and clears.
3. **A `NullHandler` subclass defined by cmdkit.** Rejected: changes the handler's type, which the
   footprint check (and anyone inspecting `cmdkit`'s handlers) sees.
4. **A module-level reference and an identity test.** Rejected in the first plan (research/01,
   option 4): a reload of the package adds a second handler that identity counts as foreign.

## Probed

| Probe | Prototype (3.9, 3.14) | `b9efaca` (3.14) |
|---|---|---|
| handler type, mark | `NullHandler`, `True` | `NullHandler`, none |
| module names starting `_null` | none | none |
| in `logging._handlers` | no | no |
| in `logging._handlerList` (shutdown) | yes | yes |
| after `importlib.reload(cmdkit)` | two `NullHandler`s, both marked | two, unmarked |

A reload's second handler carries the mark too, so the line still appears once (the `errors`
drive's reload case). `dictConfig` naming `cmdkit` drops both, as before: no handler at all, so
Python's last resort prints and cmdkit stays silent (cycle 1's F1 cases).
