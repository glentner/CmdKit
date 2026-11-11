---
status: unshaped
kind: feature
appetite: small
---

# A group with `ALLOW_NOARGS` can show its help when run bare

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

Run with no arguments, an `ApplicationGroup` prints its usage and exits 1, and a group author has no
way to ask for the full help instead. Setting `ALLOW_NOARGS = True`, the switch a plain
`Application` uses to run with no arguments, parses the empty command line: a group that requires
its `command` then fails with an argument error and exits 2 (in 2.7.7 in silence; since the
`cli-defaults` change, #33, with the message on stderr). A group whose `command` is optional
(`nargs='?'`) proceeds to its `run`, which handles `command is None`.

## Why it was deferred

It was R4 of the `cli-defaults` cycle, narrowed twice there by clarifications, and moved out after
two review rounds didn't converge; the stderr report shipped alone. What the attempts taught:

- **Decide on the effective command line.** `main(cmdline)` treats `[]` and `None` as a bare run,
  but under `ALLOW_NOARGS` 2.7.7 hands `None` to argparse, which parses `sys.argv[1:]`. A bare run
  is `[]`, or `None` with `sys.argv[1:]` empty. `None` with arguments in `sys.argv` is not a bare
  run: it dispatches, or is reported as an argument error, exactly as in 2.7.7.
- **Never pre-parse outside `main`'s handling.** The attempt parsed the command line in an
  `ApplicationGroup.main` override, before `Application.main`'s `try`. `--help`, `-h` and
  `--version` in `sys.argv` then raised `HelpOption` and `VersionOption` out of `main`, an action
  that raises escaped the group's `exceptions` map, and a side-effecting action ran twice. `main`
  must keep returning an `int` and handle every exception as 2.7.7 does (`AGENTS.md`
  § Invariants 3).
- **Only a run that would fail on the missing command changes.** A group whose `command` is
  optional keeps calling `run` on a bare run. A group that requires its `command` and is run bare
  shows its help and exits 0. Whether "would fail on the missing command" is read as "the group's
  interface rejects the bare command line" (which also covers an optional `command` beside another
  required argument) is for the shaping step.
- **Pass everything through.** An override of `main` must hand `shared` on unchanged: nested groups
  with shared options rely on it, and no test pinned it.

## Outcome / vision

A group author sets `ALLOW_NOARGS = True` and a bare run of a group that requires its command prints
exactly its `--help` output and exits 0. Every other run, bare or not, behaves byte for byte as it
does without the change.

## Sketch of the acceptance criteria

- **R1** — WHEN a group with `ALLOW_NOARGS = True` that requires its `command` runs with an empty
  effective command line (`main([])`, or `main(None)` with `sys.argv[1:]` empty), it SHALL print
  what `main(['--help'])` prints and return `exit_status.success`.
- **R2** — WHEN its effective command line is not empty, or its `command` is optional, it SHALL
  behave exactly as before the change: dispatching, `--help`, `--version`, actions, the
  `exceptions` map and argument errors included.
- **R3** — Without `ALLOW_NOARGS`, a bare group SHALL print its usage and return
  `exit_status.usage` (`test_app_group_usage` unchanged).

## Tests that would show it

- In a fresh interpreter, for a group that requires its command, one with an optional command, one
  with `ALLOW_PARSE`, one with an action that raises an exception its `exceptions` maps, and one
  nested as another group's command: `main([])`, `main()`, and `main(None)` with `sys.argv[1:]`
  empty, `['bogus']`, `['--help']`, `['--version']`, `['cmd', 'x']`, `['--bogus']` and `['cmd']`,
  each compared byte for byte (stdout, stderr, status) with the same call on 2.7.7, apart from the
  one bare case R1 changes.
- In the suite, beside `test_app_group_usage`: the bare required group's help with status 0, the
  optional group's `run`, `main(None)` with `sys.argv` patched to an unknown command (status 2), and
  a nested group's shared options passing through.
- A mutant sweep over the decision: the bare test, the opt-in, the effective command line, and
  `shared` passed on.

## Notes

- Related: `issues/cli-command-suggestions.md` and `issues/app-exception-handlers.md` (the same
  `main` paths).
- Found by: the `cli-defaults` cycle, moved out at its second review.
