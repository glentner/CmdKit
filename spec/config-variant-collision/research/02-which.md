# 02 — How `which` walks the layers

Probed against `38ff951` in fresh interpreters.

## The walk

`Configuration.which(*path)` (`src/cmdkit/config.py:150-192`) copies the layers and `_` into one
`Namespace` (`{**self.namespaces, '_': self.local}`), walks the labels from last to first, and in
each tries `sub = sub[p]` for every key on `path`. The first label whose walk succeeds is returned;
a `KeyError` moves on to the next label; anything else propagates. It never reads the merged view.

Consequences, all pinned at base:

- Through a scalar, `which` raises `TypeError` ("'int' object is not subscriptable") from the
  highest layer that holds a scalar on the way, even when a lower layer holds the path and even
  when the merged view holds a mapping there (`{x: 5}` under `{x: {z: 1}}`: `which('x', 'y')`
  raises `TypeError`, item access raises `KeyError`).
- After an in-place change replaces a value (`update(x=5)`, then `update(x={'c': 1})` over a layer
  holding `x.b`), `which('x', 'b')` names the layer although the merged view lacks it. Today's
  staleness under `_`, not a variant matter.
- After `del cfg['x']`, `which('x')` names the layer; after `Configuration(_=...)`, `which` names
  `_` for keys the merged view lacks; after a layer added after an in-place change, `which` names
  `_` for a value the late layer replaced.

## What R3 needs from it

- When the merged view holds the path, the highest source holding the literal path is the one that
  provided it, for layers and `_` applied in order: a source above it that held a scalar on the way
  would have replaced it (and the walk raises there first), and a source above it that set another
  variant at the path's place would have dropped it (so the merged view would not hold it).
  The walk is right as it is.
- When the merged view lacks the path because a higher source set another variant at a key's place
  on it, the walk finds the lower holder and names it. That is the only answer R3 changes:
  `KeyError`.
- So the change is a guard in front of the unchanged walk: item access along the path raises
  `KeyError` in the merged view, *and* some source above a source holding the path sets a sibling
  variant of a key on the path at that key's place without the key. Both conditions are needed:
  - without the first, a variant set again higher up (`token`, `token_env`, `token` again) would
    raise instead of naming the top layer;
  - without the second, the non-goal paths that already make the merged view and `which` disagree
    (item assignment, `del`, `Configuration(_=...)`, a layer after an in-place change, a scalar
    replaced in `_`) would change answer, which R7 forbids.
- A guard that looks only at the depth where the merged view lacks a key misses a section dropped
  as a whole and set again fresh higher up (`{b_eval: {b_eval: 4}}`, then `{b_env: ...}`, then
  `{b_eval: {a: ...}}`); the guard looks at every depth.
- History in `_` is folded: two in-place changes `a_env` then `a_env_eval` leave only `a_env_eval`
  in `_` (C3), and `a_env_eval` is not a variant of `a`. The guard cannot see that `a` was dropped,
  and `which('a')` names the layer that held it, as today's `which` does beneath any value an
  in-place change replaced. A wider relation (same root after stripping every suffix) would catch
  it but would change answers after `del` and item assignment outside any collision, against R7.
  Recorded in PLAN § 5.
