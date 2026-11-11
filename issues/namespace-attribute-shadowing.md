---
status: unshaped
kind: feature
appetite: small
---

# A path accessor that no method name can shadow

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`Namespace` is a `dict`, and Python resolves real attributes before `__getattr__`
(`src/cmdkit/namespace.py:80`). So a key that shares a name with a method is unreachable by
attribute, silently. That covers the `dict` methods (`items`, `keys`, `values`, `get`, `update`,
`copy`, `pop` …) and Namespace's own (`to_dict`, `whereis`, `duplicates`, the `from_*` and `to_*`
families). Probe: `Namespace({'items': 5}).items` is a bound method.

On a `Configuration`, the keys `local` and `namespaces` return its internals (`src/cmdkit/config.py:59-60`).
Probe: `Configuration(a={'local': 5}).local` is `Namespace({})`. A template that renders
`{{ cfg.server.items }}` prints a method's repr. Item access (`ns['items']`) works, but it doesn't
expand `_env` and `_eval` variants the way attribute access does.

## Why it was deferred

Attribute access to these names is fixed by Python and by consumers' code, so changing it would
change a default. Found while evaluating cmdkit for layered configuration.

## Outcome / vision

Attribute access stays as it is. An additive accessor, for example `ns.get_path('server', 'items')`,
reaches any key at any depth and expands variants exactly as attribute access does. The documentation
lists the reserved names.

## Sketch of the acceptance criteria

- **R1** — The accessor SHALL return the value at a path of keys whatever the keys are named,
  including `items`, `local` and `namespaces`.
- **R2** — WHEN the last key has an `_env` or `_eval` variant, the accessor SHALL expand it as
  attribute access does.
- **R3** — WHEN the path is missing, it SHALL raise `KeyError` naming the path, or return a given
  default.

**Test that shows it:** `Namespace({'server': {'items': 5}}).get_path('server', 'items') == 5`;
`Configuration(a={'local': {'x_env': 'HOME'}}).get_path('local', 'x') == os.environ['HOME']`; a
missing path raises `KeyError`, or returns the default when one is given.

## Notes

- Waits on `config-explicit-expansion`. Under its opt-in the accessor must return the
  already-expanded value and run nothing.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11.
