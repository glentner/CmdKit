---
status: unshaped
kind: fix
appetite: small
---

# `test_app_invalid_options` stops generating prefixes of `--help`

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`tests/test_app.py::test_app_invalid_options` draws an option name of 2 to 10 ASCII letters and
expects `DemoApp.from_cmdline(['arg_1', f'--{opt}'])` to raise `ArgumentError`, skipping only
`debug` and `option`. argparse accepts unambiguous abbreviations of long options, so `--he`,
`--hel` and `--help` select `-h/--help`, and `Interface` raises `HelpOption`, not `ArgumentError`
(falsifying example `opt='he'`). Prefixes of `--debug` (`--de`) select the `store_true` flag and
raise nothing, so the test fails with "DID NOT RAISE". Prefixes of `--option` (`--opt`) are not a
problem: the option needs a value, so the parse raises `ArgumentError` ("expected one argument")
and the test passes. Measured on `develop` (`b9efaca`), Python 3.14: 1 of 40
fixed `--hypothesis-seed` values fails, so the profile's `verify`, which runs the suite on two
Pythons, goes red now and then with no change to the code. After a failure, Hypothesis saves the
example in `.hypothesis/` and replays it, so the same checkout then fails on every run until that
directory is cleared.

## Why it was deferred

Pre-existing on `develop`; found in the cli-defaults plan step's dry run of the full suite. The
cli-defaults cycle changes `Application.main` and adds tests beside the existing ones, and keeps
every existing test unchanged; fixing this test is outside its goal. Its phase gates run
`tests/test_app.py` with a fixed Hypothesis seed that does not hit the case.

## Outcome / vision

The test asserts what it means to: an option name that is not a prefix of any defined long option
raises `ArgumentError`. It never fails by chance.

## Sketch of the acceptance criteria

- **R1** — WHEN the drawn option name is a prefix of `help` or `debug`, the test SHALL skip it (or
  assert the documented outcome for it), and otherwise SHALL assert `ArgumentError`.
- **R2** — The suite SHALL pass under any `--hypothesis-seed`, on 3.9 and 3.14.

## Notes

- Related: `issues/cli-command-suggestions.md` (edits the same test module later).
- Found by: `cli-defaults` plan step, full-suite dry run.
