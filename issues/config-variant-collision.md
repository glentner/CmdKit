---
status: unshaped
kind: fix
appetite: small
---

# A value and its `_env` and `_eval` variants are one key across layers

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

cmdkit lets a configuration value be given three ways: `token = "abc"`, `token_env = "VAR"` (read
the environment variable) or `token_eval = "cmd"` (run a shell command). Attribute access expands
the variant (`NSCoreMixin.__getattr__`, `src/cmdkit/namespace.py:80-103`). But the depth-first merge
(`namespace.py:64-74`) treats them as three unrelated keys, so when different layers of a
`Configuration` set different variants, both survive into the merged view:

```python
cfg = Configuration(user=Namespace({'hf': {'token': 'a'}}),
                    env=Namespace({'hf': {'token_env': 'HF_TOKEN'}}))
dict(cfg)               # {'hf': {'token': 'a', 'token_env': 'HF_TOKEN'}}
cfg.hf.token            # AttributeError: 'token' has more than one variant
cfg['hf']['token']      # 'a', the lower layer's stale value
cfg.which('hf', 'token')  # 'user'
```

The higher layer, which should win, either raises or loses. The reverse order (`_env` low, plain
value high) collides the same way. A user who sets `auth` in one file and `auth_eval` in another,
as HyperShell's server `auth` key invites, gets an error or the wrong value, depending on how the
value is read. It's undefined behaviour, not a design.

## Why it was deferred

Pre-existing on `develop` and in 2.7.7. Found while evaluating cmdkit for layered configuration.

## Outcome / vision

Across layers, the highest layer that sets any variant of a name decides: its variant is the only
one in the merged view, and attribute access, item access and `which` agree on it. Within a single
layer, two variants of one name are still ambiguous and still raise on attribute access. Layers
themselves are untouched. This is an outright failure, so the fix is the default (`AGENTS.md`
§ Invariants 1).

## Sketch of the acceptance criteria

- **R1** — WHEN a layer sets `name`, `name_env` or `name_eval` at a path and a lower layer set a
  different variant of `name` at the same path, the merged view SHALL hold only the higher layer's
  variant.
- **R2** — Attribute access and item access SHALL then agree with each other.
- **R3** — WHEN one layer holds two variants of a name at one path, attribute access SHALL still raise
  `AttributeError` ("has more than one variant").
- **R4** — `which(*path, name)` SHALL name the layer whose variant is in the merged view.
- **R5** — In-place changes recorded in the `_` layer (`update`, attribute assignment) SHALL follow
  the same rule.
- **R6** — No layer in `Configuration.namespaces` SHALL be modified.

**Test that shows it:** for each ordered pair of distinct variants (six cases), a two-layer
`Configuration` with the pair at `section.name`. Assert that the merged view holds only the upper
variant, that `cfg.section.name` returns the upper layer's value (set the variable; use
`echo` for `_eval`), and that `which` names the upper layer. One layer holding two variants still
raises.

## Notes

- `tests/test_config.py` `TestConfiguration.test_attribute_expand_multiple_variants` builds layer `a`
  with `nested.test` and layer `b` with `nested.test_eval` and expects the "more than one variant"
  `AttributeError`. It pins the collision, and this fix changes its expectation. The `TestNamespace`
  test of the same name (one mapping) keeps its expectation.
- Open at shaping: should plain `Namespace.update` follow the rule too? Its semantics today are
  `dict`-like, and changing them is a default change; the `Configuration` layering is where the
  failure is.
- Variants can't arrive through the environment today; `issues/environ-mapping.md` carries them, and
  they obey this rule.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11.
