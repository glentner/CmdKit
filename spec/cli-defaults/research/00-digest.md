# 00 — Digest

Two briefs, no contradictions between them.

- **The decision is a call-time walk of the handler chain** ([01](01-call-time-decision.md)): in
  the `ArgumentError` branch of `Application.main`, after `cls.log_critical(error)`, write
  `str(error)` and a newline to `sys.stderr` when `cls.log_critical == log.critical` and no
  handler other than a `logging.NullHandler` on the `cmdkit` logger would receive a `CRITICAL`
  record from `cmdkit.app`. No handler is attached, so the import-time and after-call handler sets
  are 2.7.7's.
- **The literal definition has visible edges** ([01](01-call-time-decision.md)): a disabled
  `cmdkit.app` logger (the `dictConfig` default), `logging.disable`, a handler level above
  `CRITICAL`, or `propagate = False` on `cmdkit` all mean no handler would receive the record, so
  the design writes the bare line where develop wrote nothing. PLAN carries this as a reading for
  sign-off, with the alternative that would keep those cases silent.
- **Tests hide pytest's root handlers inside the test body, never in a fixture**
  ([02](02-pytest-logging.md)); R2 uses `caplog`. The gates add fresh-interpreter drives, which
  also catch what an in-process test can't (and the reverse: a `sys.stderr` bound at import is
  caught only in-process).
- **The bare group** needs no research: `ApplicationGroup.main` maps an empty command line to
  `['--help']` when `ALLOW_NOARGS is True`, so the output is `--help`'s by construction.

No question from the research blocks the design.
