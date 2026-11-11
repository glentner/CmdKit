---
status: unshaped
kind: fix
appetite: small
---

# The merged view and `which` agree on where `_` sits

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

A `Configuration` keeps two orders for its layers, and they disagree once a layer is added after an
in-place change.

- **The merged view** applies changes in the order they arrive. `extend` merges each new layer into
  it (`src/cmdkit/config.py:89-94`), and `update` and attribute assignment merge in-place changes
  into it (`config.py:232-272`). So a layer added after an `update` overrides that change.
- **`which`** (`config.py:150-192`), `duplicates`, `whereis` and `repr` list the named layers in the
  order they were added and then put `_` last, above all of them.

On `develop` (`38ff951`):

```python
cfg = Configuration(a=Namespace({'x': 1}))
cfg.update(x=2)
cfg.extend(b=Namespace({'x': 3}))
cfg.x            # 3, from layer b
cfg.which('x')   # '_'
repr(cfg)        # Configuration(a=Namespace({'x': 1}), b=Namespace({'x': 3}), _=Namespace({'x': 2}))
```

The value and the label that explains it disagree. No variant is involved: any key shows it.

## Why it was deferred

Pre-existing on `develop` and in 2.7.7. Found while shaping `config-variant-collision`, which defines
"higher" by `which`'s precedence (layers in the order added, then `_`) and leaves this disagreement
out of its scope.

## Outcome / vision

The merged view and `which` agree on every key after any sequence of `extend`, `update` and attribute
assignment. Which order is right, `_` always on top or the order of arrival, is this seed's shaping
question. The docstring of `Configuration.update` describes `_` as the record of in-place changes,
and `which` and `repr` both show it last.

## Sketch of the acceptance criteria

- **R1** — WHEN a layer is added with `extend` after an in-place change to a key it also sets, the
  value in the merged view and the layer `which` names for that key SHALL agree.
- **R2** — Without a layer added after an in-place change, the merged view and `which` SHALL behave as
  today.

**Test that shows it:** the probe above. Assert that `cfg.which('x')` names the layer whose value
`cfg.x` returns, whichever order shaping chooses. Repeat with attribute assignment in place of
`update`, and with a nested key.

## Notes

- Choosing "`_` stays on top" changes the merged view's value in this case; choosing "order of
  arrival" changes what `which` and `repr` report. Either is a visible change, so the shaping step
  decides whether this is an outright failure under `AGENTS.md` § Invariants 1.
- `issues/config-local-layer-tracking.md` routes more in-place changes into `_`, and
  `config-variant-collision` defines its variant rule by `which`'s precedence; this cycle builds on
  both.
- Found by: shaping `config-variant-collision`, 2026-11-11.
