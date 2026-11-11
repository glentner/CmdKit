---
status: unshaped
kind: fix
appetite: small
---

# Every in-place change to a `Configuration` lands in its `_` layer

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`Configuration.update` and attribute assignment record changes in the `_` layer, so `which` can
report them (`src/cmdkit/config.py:232-272`, and its docstring). Other ways of changing the merged
view skip it:

- **Item assignment.** `cfg['x'] = 5` goes through `NSCoreMixin.__setitem__` straight to the merged
  view. `which('x')` then names the layer whose value was overwritten, and `repr(cfg)` doesn't show
  the change. Probe: `Configuration(a=Namespace({'x': 1}))`, then `cfg['x'] = 5`; `which('x')` is
  `'a'` and `cfg.local` is empty.
- **`setdefault`** (from `dict`) adds a key that no layer holds, so `which` raises `KeyError`.
- **`del cfg[key]` and `clear()`** remove keys from the merged view only, while `pop` and `popitem`
  raise `NotImplementedError` for exactly that reason (`config.py:274-286`).
- **Mutable values are shared.** A layer's list is the same object in the merged view, so
  `cfg['xs'].append(2)` changes `cfg.namespaces['a']['xs']`.

## Why it was deferred

Pre-existing on `develop`. Found by the adoption sweep.

## Outcome / vision

Item assignment and `setdefault` record into `_` exactly as `update` does, and `which` names `_`.
Layers keep their own copies of mutable values. These are failures of the documented provenance
model, so the fixes are the default.

**Default-change check:** `repr` of a configuration changed by item assignment gains its `_=…` part,
which is visible to anyone comparing reprs. `del` and `clear()` are left as they are unless shaping
decides they should match `pop`, because making them raise *would* change a default.

## Sketch of the acceptance criteria

- **R1** — WHEN a key is assigned by item on a `Configuration`, the change SHALL be recorded in the
  `_` layer, and `which` SHALL return `'_'` for it.
- **R2** — WHEN `setdefault` adds a key, the same SHALL hold.
- **R3** — WHEN a value in the merged view is mutated in place, no layer in `namespaces` SHALL change.

**Test that shows it:** `cfg = Configuration(a=Namespace({'x': 1, 'xs': [1]}))`; `cfg['x'] = 5`;
`cfg.setdefault('y', 2)`; `cfg['xs'].append(2)`. Then `cfg.which('x') == cfg.which('y') == '_'`,
`cfg.local == {'x': 5, 'y': 2}` and `cfg.namespaces['a']['xs'] == [1]`.

## Notes

- The merge itself assigns items on the `Configuration` (`__depth_first_update` writes
  `original[key] = value`, with `original` the configuration), so the fix must tell a caller's
  assignment from the merge's.
- `issues/builder-trim-local-layer.md` depends on what the `_` layer holds.
- **Two in-place sequences where `which` and item access disagree** (left by
  `spec/config-variant-collision/`, C8). Since that cycle, a variant an in-place change sets
  displaces the others in `_` too, so `_` can lose the variant that displaced a key, and `which`
  then names the layer that held it, as it does after item assignment or `del`:
  - an in-place `a_env` over a layer's `a`, then an in-place `a_env_eval`;
  - a variant displaced in place, then set again fresh in place, with a key the fresh value lacks.

  **Test that shows it:** `cfg = Configuration(l=Namespace({'a': 1, 's': {'t': 1}}))`;
  `cfg.update(a_env='X')`; `cfg.update(a_env_eval='echo y')`; `cfg.update(s_env='S')`;
  `cfg.update(s={'u': 2})`. Then `cfg['a']` and `cfg['s']['t']` raise `KeyError`, and so should
  `cfg.which('a')` and `cfg.which('s', 't')` (today both return `'l'`).
- Found by: adoption sweep, 2026-11-10.
