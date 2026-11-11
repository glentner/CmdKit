---
status: unshaped
kind: fix
appetite: small
---

# `import cmdkit` works when the process has no stderr or stdout

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`src/cmdkit/ansi.py` decides at import whether to colour output, by calling `sys.stdout.isatty()`
(line 31) and `sys.stderr.isatty()` (line 33). When either stream is `None`, importing cmdkit
raises `AttributeError: 'NoneType' object has no attribute 'isatty'`, so an application built on
cmdkit can't start at all. Python sets `sys.stderr` (or `sys.stdout`) to `None` when the process
starts with that file descriptor closed (`app 2>&-`, some daemons and service managers), and a
GUI interpreter on Windows (`pythonw`) starts with both `None`.

Probed on Python 3.9 and 3.14, with the package installed:

| Setup | Result |
|---|---|
| `sys.stderr = None`, then `import cmdkit` | `AttributeError` from `isatty` |
| `sys.stdout = None`, then `import cmdkit` | `AttributeError` from `isatty` |
| `python -I -c "import cmdkit" 2>&-` | exit status 1 |

This is pre-existing: the lines are the same in 2.7.7 on PyPI and on `develop`.

## Why it was deferred

Found by the `cli-defaults` cycle's fourth review, outside that cycle's scope (it guarded the
argument-error report's own write to stderr, not the import). Seeded by the maintainer's ruling on
that review.

## Outcome / vision

cmdkit imports, and its applications run, when `sys.stdout` or `sys.stderr` is `None`; colour is
simply off for a stream that isn't there, and `FORCE_COLOR` doesn't make it fail.

## Sketch of the acceptance criteria

- **R1** — WHEN `sys.stderr` or `sys.stdout` is `None` at import, `import cmdkit` SHALL succeed,
  and colour SHALL be off for the missing stream.
- **R2** — With a stream present, the colour decision SHALL be exactly as today (`NO_COLOR`,
  `FORCE_COLOR`, `isatty`).

## Tests that would show it

- A `python -I` child that sets `sys.stderr = None` before `import cmdkit` and then writes
  `imported` on stdout: today it fails with `AttributeError`; fixed, stdout is `imported`. The same
  with `sys.stdout = None`, reporting through a duplicate of the stderr descriptor.
- A child started with descriptor 2 closed (`subprocess.run(..., stderr=subprocess.DEVNULL)` is not
  enough; close the descriptor in a `preexec_fn`, or run it through `sh -c '... 2>&-'`) that imports
  cmdkit: today exit status 1; fixed, 0.
- The colour flags with both streams present, unchanged under `NO_COLOR` and `FORCE_COLOR`.
- Each on Python 3.9 and the newest supported Python.

## Notes

- Related: `issues/import-side-effects.md` (what importing cmdkit does at all).
- Found by: the `cli-defaults` cycle, fourth review (R4-F3).
