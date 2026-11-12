---
status: unshaped
kind: tests
appetite: small
---

# The decode-error tests cover a bare `os.PathLike`

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

A TOML or JSON file given by path that fails to decode raises the decoder's own error, with the
file's path at the head of the message. `_name_the_file` (`src/cmdkit/namespace.py:38-40`) writes
that path as `os.fspath(path)`, which is correct for every `os.PathLike`.

The tests don't pin that choice. `TestFileLoading.test_decode_error_names_file`
(`tests/test_config.py:1317-1342`) runs only with `str` and `pathlib.Path`, and
`test_decode_error_configuration` (`tests/test_config.py:1344-1357`) only with `str` and a `Path`
layer. For both kinds `str(path) == os.fspath(path)`. A change to `str(path)` would pass the whole
suite on Python 3.9 and 3.14. Yet it would name a bare `os.PathLike` (an object with only
`__fspath__`) by its default repr, `<Bare object at 0x…>: Invalid value (at line 2, column 5)`, not
by its path. `test_path_round_trip` already defines such a `Bare` class, but only for reading and
writing.

The library's behaviour is correct today. Driven by hand, a bare `os.PathLike` is named by its path
in every TOML and JSON decode error, through `from_toml`, `from_json`, `from_local` and
`Configuration.from_local`, on 3.9 and 3.14.

## Why it was deferred

Found as a hand-planted mutant in the `namespace-file-loading` review, cycle 2. That mutant pins a
deeper layer of a behaviour the suite already pins: the path's presence in the message is tested,
and only its spelling for a non-`Path` `os.PathLike` is not. The code it guards was reviewed in an
earlier cycle and did not change in the remediation the review graded. It was introduced with the
file naming on the `fix/namespace-file-loading` branch; it is not in `develop` (`386a09a`), where
decode errors name no file at all.

## Outcome / vision

The decode-error tests assert the path as `os.fspath` gives it for every kind of path the loaders
accept: `str`, `pathlib.Path`, and an object that implements only `__fspath__`. Changing how the
path is spelled fails a test.

## Sketch of the acceptance criteria

- **R1** — WHEN a TOML or JSON file given by a bare `os.PathLike` fails to decode through
  `from_toml`, `from_json`, `from_local` or `Configuration.from_local`, a test SHALL assert that the
  message starts with `os.fspath(path)`, on 3.9 and 3.14.
- **R2** — Replacing `os.fspath(path)` with `str(path)` in the file naming SHALL fail that test.

## Notes

- Related: `issues/namespace-file-loading.md` (the cycle that added the file naming and these
  tests).
- Found by: `namespace-file-loading` review cycle 2, a surviving hand-planted mutant.
