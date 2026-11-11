---
status: unshaped
kind: fix
appetite: small
---

# `Environ.expand` works without a prefix

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`Environ.expand` strips the prefix by computing `len(self._prefix) + 1` (`src/cmdkit/namespace.py:443`).
`_prefix` is `None` in three documented paths, and each raises
`TypeError: object of type 'NoneType' has no len()`:

- `Environ().expand()`;
- `Namespace({'a': {'b': 1}}).to_env().expand()`: `to_env` (`:271-273`) builds an `Environ` with no
  prefix, so the round trip fails;
- `Configuration.from_local(env=True)` without `prefix=` (`src/cmdkit/config.py:115-116`).

`Configuration.from_local` also calls `Environ.reduce`, the alias its own docstring marks deprecated.

## Why it was deferred

Pre-existing on `develop`. Found by the adoption sweep.

## Outcome / vision

These are outright failures, so the fix is the default:

- with no prefix, `expand` treats every key as unprefixed: `to_env().expand()` round-trips, and
  `Environ().expand()` is empty;
- `from_local(env=True)` without a prefix raises a `ValueError` that says a prefix is required,
  rather than reading the whole environment;
- `from_local` calls `expand`.

## Sketch of the acceptance criteria

- **R1** — WHEN an `Environ` has no prefix, `expand` SHALL split each key on `_`, as it does after
  stripping a prefix.
- **R2** — `Namespace(d).to_env().expand()` SHALL equal `Namespace(d)` for nested data whose keys
  contain no `_` and whose values survive coercion.
- **R3** — WHEN `Configuration.from_local` is called with `env=True` and no `prefix`, it SHALL raise
  `ValueError` naming `prefix`.

**Test that shows it:** `Namespace({'a': {'b': 1}, 'c': 'x'}).to_env().expand() == {'a': {'b': 1},
'c': 'x'}`; `Environ().expand() == {}`; `pytest.raises(ValueError, match='prefix')` around
`Configuration.from_local(env=True)`.

## Notes

- `issues/environ-mapping.md` changes the same code and waits on this.
- Found by: adoption sweep, 2026-11-10.
