# 01 — Where the merge happens, and how layers and `_` are built

Probed against `38ff951` in fresh interpreters (`uv run --isolated --no-project --with-editable .`).

## The merge

- `NSCoreMixin.update` (`src/cmdkit/namespace.py:76-78`) calls the name-mangled classmethod
  `__depth_first_update(original, new)` (`:64-74`): for each key of `new`, descend when both
  values are `dict` (`isinstance(value, dict) and isinstance(original.get(key), dict)`), otherwise
  `original[key] = value`. The descent test is `dict`, not `Mapping`.
- Every assignment goes through `NSCoreMixin.__setitem__` (`:49-54`), which stores a mapping as a
  fresh `Namespace` (`_as_namespace(dict(value))`, recursive). So the merged view never shares a
  mapping object with a layer or with the caller's argument; only non-mapping leaves (lists) are
  shared. Deleting from the merged view's own sub-namespaces cannot reach a layer.
- `Configuration.extend` (`src/cmdkit/config.py:89-94`) stores `Namespace(mapping)` under
  `self.namespaces[name]` (itself copied again by `__setitem__`), then `super().update(layer)`:
  the merged view is the fold of layers in the order they arrive. `extend(_=m)` goes to
  `self.local.update(m)` only, never to the merged view (the `Configuration(_=...)` non-goal).
- `Configuration.update` (`:239-272`) runs `self.local.update(*args, **kwargs)` then
  `super().update(*args, **kwargs)`: each side calls `dict(*args, **kwargs)` separately. A
  one-shot iterable of pairs therefore reaches `_` and not the merged view (probe:
  `cfg.update(iter([('y', 2)]))` leaves `dict(cfg) == {'x': 1}`, `cfg.local == {'y': 2}`). Not a
  variant collision; R7 keeps it.
- `Configuration.__setattr__` (`:232-237`): `name in self` → `self.update({name: value})`, else
  `NSCoreMixin.__setattr__`, which also tests `name in self` and falls to `object.__setattr__`.
  `__init__` sets `local` and `namespaces` through it while `self` is empty.

## Expansion

- `NSCoreMixin.__getattr__` (`:80-95`) looks for `item`, `item_env`, `item_eval` in `self`; zero
  raises "not found", one expands, two or more raise "has more than one variant". `_env` reads
  `os.getenv(str(value))`, `_eval` runs `subprocess.check_output(str(value), shell=True)`. Both are
  looked up as module attributes at call time, so a spy on `os.getenv` and
  `subprocess.check_output` sees every expansion. Nothing else in either module calls them
  (probe: construction, `extend`, `dict()`, item access, `repr`, `which` make no call).

## Collision today (the defect)

- Two layers setting `token` and `token_env` at one path keep both in the merged view; attribute
  access raises, item access returns the lower value, `which` names whichever layer holds the
  literal key. The reverse order is the same.
- `Configuration.update(token='a')` then `update(token_env='X')` leaves both in `_` and in the merged
  view.
- `cfg.token = 'v'` with only `token_env` in the merged view sets an instance attribute; `_` and the
  merged view are untouched (C4).

## Neighbours pinned at base (must not move)

- A mapping and a scalar under one key replace each other, both ways.
- Keys that are not strings merge like any other key (`{1: 'a'}` then `{1: 'c'}`), and a string
  `'1_env'` beside an integer `1` keeps both.
- A layer added after an in-place change wins in the merged view while `which` names `_` (C5).
- Item assignment and `del` change the merged view only; `which` still names the layer.
- `Configuration(_=...)` records into `_` only; `which` names `_` for its keys.
- Plain `Namespace.update` keeps both variants; attribute access on it raises.
