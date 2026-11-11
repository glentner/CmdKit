---
status: unshaped
kind: feature
appetite: big
---

# Each value knows where it came from

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`Configuration.which(*path)` (`src/cmdkit/config.py:247-291`) returns a layer **label** only. It has
no file path, no environment variable name, and no command-line flag. It raises a bare
`KeyError('Not found: (...)')` on a miss. For a table path it names the highest layer that touches
the table, not a single source, as its own docstring warns.

The facts are known at load and then dropped:

- `Configuration.from_local` holds each file's path (`config.py:210-211`);
- `Environ.expand` holds each variable's name (`src/cmdkit/namespace.py:444-449`).

An application that wants to say "`server.port` = 8080, from `~/.app/config.toml`" rebuilds the
answer itself. Rebuilding a variable name by joining uppercased key parts is wrong as soon as a key
contains `_`. Error messages can't name a source either (`ConfigurationError` is an empty subclass,
`config.py:32-33`).

## Why it was deferred

Pre-existing; a feature, not a defect. Found while evaluating cmdkit for layered configuration.

## Outcome / vision

The source of each leaf is recorded at load: its layer label plus the file path, the environment
variable's name, the command-line flag, or nothing for a mapping built in code. A new accessor
returns that record for a path. `which` keeps returning a label, so this is purely additive.
`from_local`, `from_context` and `Environ` record their sources without being asked; a layer passed
in as a plain mapping can carry a source through a keyword. A miss raises a `KeyError` subclass
that names the path, so existing `except KeyError` still works.

## Sketch of the acceptance criteria

- **R1** — WHEN a `Configuration` is built by `from_local` or `from_context`, the source of each leaf
  SHALL be recorded: layer label, plus the file path or the environment variable name.
- **R2** — The provenance accessor SHALL return, for a leaf path, the layer and the source of the value
  in the merged view, including a winning `_env`/`_eval` variant.
- **R3** — Changes recorded in the `_` layer SHALL report layer `'_'` and no source.
- **R4** — `which` SHALL return exactly what it returns today for every path.
- **R5** — WHEN a path is missing, the accessor and `which` SHALL raise a `KeyError` (or a subclass)
  whose message names the path.

**Test that shows it:** two files under `tmp_path` and `APP_A_X` in the environment;
`Configuration.from_local(user=u, local=l, env=True, prefix='APP')`. The source of `a.x` is
(`'env'`, `'APP_A_X'`); the source of a key only in `l` is (`'local'`, `str(l)`). `which` gives the same
labels as before.

## Notes

- Waits on `namespace-file-loading` (paths as `os.PathLike`), `environ-without-prefix` and
  `config-local-layer-tracking`. It also waited on `config-variant-collision` (a variant's
  provenance), which landed in #35.
- `config-explicit-expansion` uses this to put the key, layer and source in its errors, and
  `environ-mapping` records the exact variable name through it.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11.
