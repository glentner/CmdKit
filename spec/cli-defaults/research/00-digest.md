# 00 — Digest

Two briefs, no contradictions between them.

- **The decision is a call-time walk of the handler chain** ([01](01-call-time-decision.md)): in
  the `ArgumentError` branch of `Application.main`, after `cls.log_critical(error)`, write
  `str(error)` and a newline to `sys.stderr` when `cls.log_critical == log.critical` and Python's
  last resort would print the `CRITICAL` record from `cmdkit.app` were cmdkit's `NullHandler` not
  there (GOAL C6). No handler is attached, so the import-time and after-call handler sets are
  2.7.7's.
- **Silenced stays silent** ([01](01-call-time-decision.md)): the first draft's literal reading
  wrote in setups applications use to silence logging (`dictConfig`'s default, `logging.disable`,
  handlers levelled above `CRITICAL`). The sign-off ruled C6, under which they stay silent and
  only `propagate = False` on `cmdkit` (where Python itself would use its last resort) changes.
- **Tests hide pytest's root handlers inside the test body, never in a fixture**
  ([02](02-pytest-logging.md)); R2 uses `caplog`. The gates add fresh-interpreter drives, which
  also catch what an in-process test can't (and the reverse: a `sys.stderr` bound at import is
  caught only in-process).
- **The bare group** needs no research: `ApplicationGroup.main` maps an empty command line to
  `['--help']` when `ALLOW_NOARGS is True`, so the output is `--help`'s by construction.

No question from the research blocks the design.
