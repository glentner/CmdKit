---
status: unshaped
kind: fix
appetite: small
---

# `BuilderConfiguration.trim` handles the `_` layer, and can drop a key from every layer

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

- **A nested duplicate in `_` crashes.** `BuilderConfiguration.trim`
  (`src/cmdkit/contrib/builder.py:149-163`) looks up a nested duplicate as `config.namespaces[space]`
  (`:155`). The `_` layer lives in `config.local`, not in `namespaces`, so a nested duplicate in
  `_` raises `KeyError: '_'`. Probe: `BuilderConfiguration(one=Namespace({'s': {'x': 1}}))`, then
  `update(s={'x': 2})`, then `trim()`.
- **`ordered=True` works by accident.** It tests `if reversed:` (`:147`), the builtin, which is always
  true, so `ordered=True` always reverses the order. The documented results depend on it. A reader who
  "fixes" it to `reverse` breaks `trim(ordered=True)`.
- **The module's TODO** (`:9-11`) asks for a new-like object with a `pop`/`popitem` modification.
  `Configuration` itself refuses `pop` and `popitem` (`src/cmdkit/config.py:274-286`), so there is no
  way to drop a key from every layer at once.

## Why it was deferred

Pre-existing on `develop`. Found by the adoption sweep, including the module's own TODO.

## Outcome / vision

- `trim` treats `_` like any other layer.
- Line 147 says what it does, with the documented results unchanged.
- A builder method (for example `without(*path)`) returns a new configuration with a key removed
  from every layer, `_` included.

The TODO's other item, moving `_find_the_leaves` into the class, has no behaviour of its own and is
left to the plan.

## Sketch of the acceptance criteria

- **R1** — WHEN a nested key is duplicated between a layer and `_`, `trim` SHALL keep the copy its
  ordering selects and SHALL NOT raise.
- **R2** — The examples in the `trim` docstrings SHALL hold as tests.
- **R3** — `without(*path)` SHALL return a new `BuilderConfiguration` in which no layer holds the path,
  leaving the original unchanged.

**Test that shows it:** the probe above returns a configuration whose `_` keeps `s.x == 2` and whose
`one` no longer holds `s.x`. `tests/test_contrib/test_builder.py`'s `test_trim_ordered` passes
unchanged. `without('s', 'x')` on a two-layer configuration leaves `s` empty in both layers, and the
original untouched.

## Notes

- Waits on `config-local-layer-tracking`, which settles what `_` holds.
- Found by: adoption sweep, 2026-11-10.
