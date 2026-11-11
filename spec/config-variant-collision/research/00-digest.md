# 00 — Digest

Research ran because the change touches `src/cmdkit/config.py`, on the high-blast-radius list
(trigger 2), scaled to the small appetite: two briefs, written in the planning session from code
reading and probes against `38ff951` in fresh interpreters.

- [`01-merge-and-layers.md`](01-merge-and-layers.md): the merge is `NSCoreMixin`'s depth-first
  update; every stored mapping is a fresh copy, so pruning the merged view can never reach a layer;
  `extend(_=...)` touches `_` only; `update` builds its argument twice; attribute assignment keys on
  `name in self`; expansion goes only through `os.getenv` and `subprocess.check_output`, looked up
  at call time.
- [`02-which.md`](02-which.md): `which` walks the layers top down and never reads the merged view;
  it is already right whenever the merged view holds the path, and wrong only where a higher source
  displaced a variant on the path.

Decisions (no contradiction between the briefs):

1. The rule lives in `src/cmdkit/config.py` only. `namespace.py` stays byte for byte: plain
   `Namespace.update` is a non-goal, and the depth-first update is reused, not copied, by pruning
   the target before it runs.
2. The prune descends exactly where the depth-first update will (both values `dict`), so it acts at
   every level the merge reaches and nowhere else.
3. `Configuration.update` keeps calling `dict(*args, **kwargs)` once per side, so a one-shot
   iterable still reaches only `_` (R7).
4. `which` gets a guard in front of its unchanged walk (02, "What R3 needs").
5. `Configuration(_=...)` (`extend(_=...)`) keeps the plain update (a non-goal).

Questions raised about how an R-ID reads: three, each carried by the design and recorded in
PLAN § 3 as a reading row, none blocking: attribute assignment of a suffixed name (`cfg.token_env =
v` over `token`) is an in-place change; `which` beneath a value an in-place change replaced keeps
today's answer; a key ending in `_env` is a variant of two names (`token_env` of `token` and of
`token_env`).
