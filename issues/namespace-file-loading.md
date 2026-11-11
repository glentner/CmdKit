---
status: unshaped
kind: fix
appetite: small
---

# File loading accepts paths and handles, and its errors name the file

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

The `Namespace` loaders (`src/cmdkit/namespace.py:130-240`) fail in four ways, each probed on
`develop` under Python 3.9 and 3.14:

- **Decode errors don't name the file.** `Namespace.from_toml` lets `tomllib.TOMLDecodeError` out
  with a line and column only (`Invalid value (at line 2, column 5)`), and so does
  `Configuration.from_local(system=…, user=…, local=…)`. A user with several configuration files
  can't tell which one is broken. JSON errors (`json.JSONDecodeError`) are the same; YAML's already
  name the stream.
- **`pathlib.Path` is rejected.** Each loader tests `isinstance(path_or_file, str)`, so a `Path` takes
  the file-object branch and fails with `AttributeError: 'PosixPath' object has no attribute 'read'`.
  Through `from_local` that becomes `NotImplementedError: type does not currently support 'toml'
  files`.
- **`from_local` masks errors.** It wraps the loader call in `try/except AttributeError`
  (`:160-164`), so any `AttributeError` raised while loading is reported as an unsupported format.
  Its message uses `cls.__class__.__name__`, which in a classmethod is `type` ("type does not
  currently support 'ini' files"). `to_local` (`:209-213`) masks the same way, and its message ends
  in a stray `."`.
- **A binary TOML handle fails.** `from_toml` calls `toml.loads(path_or_file.read())` on a handle
  (`:187`), so the binary handle that `tomllib.load` itself requires raises
  `TypeError: Expected str object, not 'bytes'`.

## Why it was deferred

Pre-existing on `develop`. The first was found while evaluating cmdkit for layered configuration,
the rest by the adoption sweep.

## Outcome / vision

Each of these is an outright failure, so each fix is the default (`AGENTS.md` § Invariants 1):

- a decode error keeps its type, so code that catches `tomllib.TOMLDecodeError`,
  `json.JSONDecodeError` or `ValueError` still catches it, and its message names the file;
- every loader and writer accepts `str` and `os.PathLike`;
- an unsupported extension raises `NotImplementedError` naming the class and the extension, and an
  error raised inside a loader propagates unchanged;
- `from_toml` reads text and binary handles alike.

## Sketch of the acceptance criteria

- **R1** — WHEN a TOML or JSON file fails to decode, the raised error SHALL be an instance of the
  decoder's own error type, and its message SHALL contain the file's path.
- **R2** — `from_local`, `from_toml`, `from_yaml`, `from_json`, `to_local` and the `to_*` writers SHALL
  accept an `os.PathLike` wherever they accept a path string.
- **R3** — WHEN a loader raises, `from_local` SHALL let that exception through unchanged.
- **R4** — WHEN the extension is unsupported, the `NotImplementedError` message SHALL name the class
  (`Namespace` or the subclass) and the extension.
- **R5** — `from_toml` SHALL load from a binary handle and from a text handle.

**Test that shows it:** write `[a]\nx = \n` to `tmp_path / 'bad.toml'`. `Configuration.from_local(user=…)`
raises the TOML decoder's error, and `str(path)` is in its message; the same for JSON. A
`Namespace.from_local(tmp_path / 'c.toml')` round trip for all three formats. A subclass whose
`from_json` raises `AttributeError('inner')` surfaces that error from `from_local`. A
`from_local('x.ini')` message names `Namespace`. `from_toml(open(p, 'rb'))` loads.

## Notes

- On 3.9 and 3.10 the decoder is `tomli`, and its error type is `tomli.TOMLDecodeError`.
- Python 3.14's `TOMLDecodeError` takes `(msg, doc, pos)`; whether the fix re-raises a subclass or
  rebuilds the message is the plan's call.
- `Namespace({'a': None}).to_toml(…)` raises `TypeError` because TOML has no null. That's TOML, not a
  defect; record it as accepted if it comes up.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11 (decode errors), and the
  adoption sweep, 2026-11-10 (the rest).
