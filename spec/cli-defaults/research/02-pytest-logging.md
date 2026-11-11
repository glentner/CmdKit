# 02 — pytest's logging plugin and in-process tests of the stderr report

**Question.** pytest's logging plugin attaches handlers to the root logger during a test. How do
the in-process tests of R1 see "no logging configured", and how do the tests of R2 and R3 stay
honest (GOAL "How it is shown" 1)?

## What pytest attaches (probed, pytest 8 on 3.9 and 3.14)

During both the setup and the call phase of a test the root logger carries four handlers, all at
level 0: `_LiveLoggingNullHandler` (a `NullHandler` subclass), `_FileHandler` (to `os.devnull`
unless `log_file` is set) and two `LogCaptureHandler`s (the report capture and `caplog`'s). They
are added and removed per phase with `root.addHandler` / `root.removeHandler` on the root logger's
own list (`catching_logs`).

Consequences:

- Under pytest, `cmdkit.app` always has receiving handlers, so an in-process `main` call hits R2,
  never R1, unless the test hides them.
- Hiding them in a **fixture** does not work: fixtures run in the setup phase, and the call phase
  adds its own handlers afterwards. Swapping `root.handlers` for a new list with `monkeypatch` is
  worse: `catching_logs.__exit__` then removes its handler from the new list, and `monkeypatch`
  restores the old list with the call-phase handlers still in it, so they leak into every later
  test.
- Hiding them **inside the test body**, by saving `root.handlers[:]`, clearing the list in place,
  and restoring it in place in a `finally`, is exact: all within the call phase, nothing leaks.
- `capsys` replaces `sys.stdout` and `sys.stderr` for the test; a write to `sys.stderr` looked up
  at call time is captured, one bound at import is not (the mutant that binds `sys.stderr` at
  import fails the in-process tests and passes a subprocess drive, so both are needed).
- `caplog` gives R2 its configured handler for free: the record arrives in `caplog.records`, and
  `capsys` shows that cmdkit wrote nothing to stderr.

## Choice

- **Tests in `tests/test_app.py`** stay in-process: a small context manager in the test module
  hides the root handlers inside the test body (R1, R3 with no handler behind the replacement,
  R7's no-handler-left check); R2 uses `caplog`; R4 and R5 need no logging setup at all.
- **The phase gates** also drive `main` in fresh child interpreters (`python -I -c ...`), where no
  test runner is present: that is GOAL's "fresh interpreter" demonstration for R1, R2, R3 and R7,
  and it covers `logging.basicConfig`, a handler on the `cmdkit` logger, and a decision taken per
  call.
