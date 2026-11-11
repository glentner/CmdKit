---
status: unshaped
kind: feature
appetite: big
---

# Hand-written help stays first-class; argparse's generated help is the fallback

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`Interface(program, usage_text, help_text, …)` (`src/cmdkit/cli.py:62-77`) requires hand-written
usage and help. It returns them from `format_usage` and `format_help` (`:80-85`), colorized by
`colorize_usage` (`src/cmdkit/ansi.py:88-109`) unless colour is off. That's cmdkit's design, and it
stays. But there is no other path. An application that just wants argparse's generated help from its
`add_argument` calls must still write both texts, and keep them in step with its options by hand.

Meanwhile argparse has moved. Python 3.14 colours its own help (`ArgumentParser(color=…)`) and can
suggest close matches (`suggest_on_error`); neither exists on 3.9–3.13.

`colorize_usage` and the `ansi` module have no tests, so a change here can't show that hand-written
output is unchanged.

## Why it was deferred

A feature, and it touches the `--version` override (`issues/import-side-effects.md`) and the help
path in `Application.main`. Raised by the maintainer, 2026-11-10.

## Outcome / vision

- **Hand-written usage and help are unchanged:** printed as written, colorized by `colorize_usage`,
  `disable_colors` and `formatter=` still honoured.
- **The fallback:** when an application supplies no usage or no help text, `Interface` uses argparse's
  generated text for it. On 3.14+ argparse colours it, following `NO_COLOR` and `FORCE_COLOR` the way
  cmdkit does; whether older Pythons get `colorize_usage` or plain text is decided at shaping. `-h`
  still raises `HelpOption` with the text, and `Application.main` prints it.
- The seed's first deliverable is the survey: what 3.9–3.14 argparse offers, and how it meets cmdkit's
  formatter and its version action.

## Sketch of the acceptance criteria

- **R1** — WHEN `Interface` is given usage and help text, `format_usage` and `format_help` SHALL
  return exactly what 2.7.7 returns, colour on or off.
- **R2** — WHEN help text is omitted, `-h` SHALL raise `HelpOption` whose text lists every argument
  added with `add_argument`, with its help string.
- **R3** — WHEN usage text is omitted, argument errors and a bare run SHALL show argparse's generated
  usage.
- **R4** — Generated help SHALL carry no ANSI codes WHILE `NO_COLOR` is set or stdout is not a terminal,
  unless `FORCE_COLOR` is set.

**Test that shows it:** golden tests first: `colorize_usage` over the usage and help in
`tests/test_app.py` with colour forced, compared byte for byte to 2.7.7's output. Then
`Interface('prog')` with `--count` (`help='how many'`): `parse_args(['-h'])` raises `HelpOption` whose
text contains `--count` and `how many`. With `NO_COLOR=1`, the text contains no `\033[`.

## Notes

- Waits on `import-side-effects` (`cli.py`). It also waited on `cli-defaults` (the help path in
  `app.py`), which landed in #33.
- Found by: maintainer request, 2026-11-10.
