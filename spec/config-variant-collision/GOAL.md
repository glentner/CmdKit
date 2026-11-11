# GOAL — A value and its `_env` and `_eval` variants are one key across layers

> **Origin spec.** The *what* and *why*: the locked contract the review grades against.
> The *how* lives in [`PLAN.md`](PLAN.md) and [`TECH.md`](TECH.md), written by the plan step.
> Edit requirements here; do **not** silently drift them during build.

- **slug:** config-variant-collision
- **kind:** fix
- **appetite:** small

## Problem

cmdkit lets a configuration value be given three ways: `token = "abc"`, `token_env = "VAR"` (read
the environment variable) or `token_eval = "cmd"` (run a shell command and take its output).
Attribute access expands the variant it finds (`NSCoreMixin.__getattr__`,
`src/cmdkit/namespace.py:80-103`). A `Configuration` builds its merged view by applying each layer
with the depth-first update (`namespace.py:64-78`, reached from `Configuration.extend`,
`src/cmdkit/config.py:89-94`), and that update treats `token`, `token_env` and `token_eval` as
three unrelated keys. When two layers set different variants of one name, both survive into the
merged view. On `origin/develop` (`38ff951`):

```python
cfg = Configuration(user=Namespace({'hf': {'token': 'a'}}),
                    env=Namespace({'hf': {'token_env': 'HF_TOKEN'}}))
dict(cfg)                  # {'hf': {'token': 'a', 'token_env': 'HF_TOKEN'}}
cfg.hf.token               # AttributeError: 'token' has more than one variant
cfg['hf']['token']         # 'a', the lower layer's stale value
cfg.which('hf', 'token')   # 'user'
```

The higher layer, which should win, either raises or loses, depending on how the value is read. The
reverse order (a variant low, the plain value high) collides the same way. A user who sets `auth` in
one file and `auth_eval` in another, as HyperShell's server `auth` key invites, gets an error or the
wrong value. In the maintainer's words, this is "undefined behavior and not intended".

The defect is pre-existing: the merge dates from 3d09f1b (2023-09) and the expansion from 79d81c8
(2023-10, "Fix broken _env and _eval expansion"), and both shipped in 2.7.7. `AGENTS.md`
§ Invariants 2 records it as a known limitation. Under § Invariants 1 it is an **outright failure**:
an exception, or a silently wrong value, where the documented layering has an answer. So the fix is
the default, not an opt-in. The test that pins the old behaviour is
`TestConfiguration.test_attribute_expand_multiple_variants` in `tests/test_config.py` (R7).

## Outcome / vision

Across layers, `name`, `name_env` and `name_eval` behave as one key. The highest layer that sets any
variant of a name decides: the variants it sets are the only ones in the merged view, and attribute
access, item access and `which` agree on them. Within a single layer, two variants of one name are
still ambiguous and still raise on attribute access, exactly as a `Namespace` does today. Layers
themselves are never modified. In-place changes recorded in the `_` layer follow the same rule.
Everything that involves no variant collision behaves as it does today.

In this document, a *variant* of `name` is any of the keys `name`, `name_env` and `name_eval` in one
mapping, and the *path* of a key is its sequence of enclosing keys (empty at the top level). "Higher"
means later in the precedence `which` already reports: the layers in the order they were added, then
`_` (C5). A key ending in `_env` or `_eval` is a variant by its suffix alone, as attribute access
already treats it, whatever the user meant by it (C2).

## Acceptance criteria (the contract)

- **R1** — WHEN a layer sets one or more variants of `name` at a path, and a lower layer set a
  different variant of `name` at the same path, the merged view SHALL hold, at that path, only the
  variants the higher layer sets. This holds at the top level and at any depth, and whatever the
  values are, mappings included. `dict(cfg)` and iteration over the merged view show it.
  Today both layers' variants survive.
- **R2** — In R1's case, attribute access (`cfg.section.name`) SHALL return the higher layer's value,
  expanded as its variant says (the value itself, the environment variable, or the command's
  output), and item access SHALL agree with it: the higher variant's own key returns its raw value,
  and the key of any variant only a lower layer set raises `KeyError`. Today attribute access raises
  "has more than one variant" and item access returns the lower layer's stale value.
- **R3** — `cfg.which(*path, key)` SHALL stay keyed on the literal `key` and SHALL answer from the
  merged view, agreeing with item access (C1). In R1's case it SHALL name the higher layer for the
  key of a variant in the merged view, and SHALL raise `KeyError` for the key of a variant only a
  lower layer set. A bare name whose only variants in the merged view are `name_env` or `name_eval`
  SHALL raise `KeyError`, as today. Today `which` names whichever layer last set the literal key, so
  in R1's case it names a lower layer whose value the merged view should not hold.
- **R4** — IF the deciding layer itself sets two or more variants of `name` at one path, THEN the
  merged view SHALL hold those variants (and no lower layer's), and attribute access SHALL raise
  `AttributeError` with "'name' has more than one variant", as today. A single `Namespace` holding two
  variants keeps today's behaviour in full: `TestNamespace.test_attribute_expand_multiple_variants`
  keeps its expectation.
- **R5** — WHEN an in-place change (`Configuration.update`, or attribute assignment of a parameter)
  sets a variant of `name` at a path where the merged view holds a different variant, the change
  SHALL be recorded in `_`, the merged view SHALL hold only the new variant, attribute access and
  item access SHALL agree with it as in R2, and `which` SHALL name `_`. This SHALL also hold:
  - WHEN a later in-place change sets a different variant of a name an earlier in-place change set
    at the same path: the later variant SHALL replace the earlier one in `_` and in the merged view,
    so `_` does not hold both (C3). One change that sets two variants at once is R4's ambiguity.
  - WHEN attribute assignment on a `Configuration` sets a top-level `name` and the merged view holds
    any variant of `name`, with or without a collision: it SHALL be an in-place change under this
    requirement. Today, when the merged view holds `name_env` or `name_eval` but not `name`, it sets
    an ordinary Python attribute and nothing reaches `_` or the merged view (C4).

  Plain `Namespace.update` is unchanged: the replacement belongs to how a `Configuration` records
  its in-place changes.
- **R6** — No layer in `Configuration.namespaces` SHALL be modified by construction, `extend`,
  `update`, attribute assignment or attribute access: after any of them, each layer still equals the
  mapping it was built from. Loading, construction, merging, item access and `dict()` SHALL still
  never read an `_env` variable or run an `_eval` command (§ Invariants 2).
- **R7** — Everything outside a variant collision, apart from R5's top-level attribute assignment
  (C4), SHALL behave as today: the depth-first merge of one
  key set by several layers, plain `Namespace` updates and attribute access, `which` for keys no
  collision touches, and `whereis` and `duplicates`. Every test collected from `tests/` at `38ff951`
  SHALL still pass unchanged except `TestConfiguration.test_attribute_expand_multiple_variants`.
  That test (layer `a` sets `nested.test`, layer `b` sets `nested.test_eval = 'echo bar'`) SHALL
  instead expect `cfg.nested.test == 'bar'`, with `cfg.nested.a == 1`, `cfg.nested.b == 2` and
  `cfg.other.secret == 'baz'` still holding, and no `AttributeError`.
- **R8** — The documentation SHALL state the rule, in the same commit as the code (§ Conventions):
  the `Configuration` docstring and the passage of `docs/index.rst` that introduces `_env` and
  `_eval`. In `AGENTS.md` § Invariants 2, the known-limitation line for the collision SHALL be
  replaced by a line stating the rule: "`name`, `name_env` and `name_eval` are one key across
  layers: the highest layer that sets any of them decides" (C6).

**How it is shown.**

1. For each ordered pair of distinct variants of one name (six cases), a two-layer `Configuration`
   with the pair at `section.name`: the merged view holds only the upper variant (R1); attribute
   access returns the upper layer's value, with the variable set for `_env` and `echo` for `_eval`,
   and item access agrees (R2); `which` names the upper layer for the upper variant's key and raises
   `KeyError` for the lower one's (R3); both layers still equal their inputs (R6). One case repeated
   at the top level and one three levels deep. One case uses a key the user did not mean as a
   variant (`conda` low, `conda_env` high: `cfg['conda']` raises `KeyError`, C2).
2. A lower layer with one variant under an upper layer with the other two: attribute access raises
   "has more than one variant" and the lower variant is absent (R4).
3. R5's in-place cases: `update` over a layer's different variant; two successive `update` calls
   with different variants (`_` holds only the later one); and top-level attribute assignment of
   `name` over a merged view holding `name_env`, from one layer and from a collision. Each time `_`
   records the change and `which` names `_`.
4. A command and a variable that record their use (an `_eval` that writes a marker under `tmp_path`,
   an `_env` read through `monkeypatch`) show that construction, merging, item access and `dict()`
   neither run nor read anything (R6).
5. The profile's `verify` on both Pythons, with only the one test's expectation changed under
   `tests/` apart from new tests (R7).

## Non-goals (no-gos)

- **Plain `Namespace.update` semantics.** It stays `dict`-like within the depth-first descent: a
  `Namespace` updated with a different variant keeps both, and attribute access on it raises as
  today. The rule lives in how a `Configuration` layers its namespaces (ruling, 2026-11-11).
- **Within-layer ambiguity.** Two variants in one layer still raise on attribute access; nothing
  picks one (R4).
- **Changing the expansion itself**: what `_env` returns when the variable is unset, how `_eval` runs
  or strips its output, and when expansion happens. That is the opt-in of
  `issues/config-explicit-expansion.md`.
- **Variants arriving through the environment.** `Environ` cannot produce `name_env` today;
  `issues/environ-mapping.md` carries that, and its variants will obey this rule.
- **Other in-place paths that bypass `_`**: item assignment, `setdefault`, `del`, `clear()`, shared
  mutable values, and attribute assignment below the top level (`cfg.section.name = v`, which writes
  to the merged view's own sub-namespace). These are `issues/config-local-layer-tracking.md`.
- **The order of `_` against a layer added after an in-place change.** Today the merged view applies
  layers in the order they arrive, so a layer added with `extend` after an `update` wins in the
  merged view while `which` names `_`. This predates the cycle and involves no variant (C5). It is
  recorded as `issues/configuration-layer-order.md`, and this cycle's tests do not add a layer after
  an in-place change.
- **Provenance beyond a layer label.** `which` keeps returning a label;
  `issues/config-provenance.md` adds the richer accessor.
- **`Configuration(_=...)`**, which records into `_` without touching the merged view.

## Clarifications

Carried from the seed and ruled by the maintainer (2026-11-11):

- **Q:** Kind and appetite? — **A:** `fix`, `small`, from the seed's frontmatter (resolved
  2026-11-11).
- **Q:** Default or opt-in? — **A:** Default. "auth, auth_env, auth_eval colliding is undefined
  behavior and not intended": an outright failure under § Invariants 1 (resolved 2026-11-11; R1–R5).
- **Q:** What decides across layers? — **A:** The highest layer that sets any variant of a name. Its
  variant is the only one in the merged view, and attribute access, item access and `which` agree
  (resolved 2026-11-11; R1–R3).
- **Q:** Within one layer? — **A:** Still ambiguous; attribute access still raises (resolved
  2026-11-11; R4).
- **Q:** May layers be modified? — **A:** Never (resolved 2026-11-11; R6).
- **Q:** Which existing test changes? — **A:** `TestConfiguration.test_attribute_expand_multiple_variants`
  only; the `TestNamespace` test of the same name keeps its expectation (resolved 2026-11-11; R4,
  R7).
- **Q:** Do in-place changes recorded in `_` follow the rule? — **A:** Yes, `update` and attribute
  assignment (resolved 2026-11-11; R5).
- **Q:** Does plain `Namespace.update` follow the rule too (the seed's open question)? — **A:** No,
  not in this cycle; it stays `dict`-like and the fix is scoped to `Configuration` (resolved
  2026-11-11; Non-goals).

Raised during shaping, ruled by the maintainer (2026-11-11):

- **C1 · Q:** In R1's case, what does `which` return for the key of a variant only a lower layer
  set (`which('hf', 'token')` when the upper layer set `token_env`), and for a bare name when the
  merged view holds only a variant of it (today `KeyError`, collision or not)? — **A:** `which`
  stays keyed on the literal key and answers from the merged view: `KeyError` in both cases,
  agreeing with item access (resolved 2026-11-11; R3).
- **C2 · Q:** Does the rule apply to every key ending in `_env` or `_eval`, including one the user
  never meant as a variant? — **A:** Yes, by suffix, as attribute access already treats such keys.
  With `conda = "x"` in one layer and `conda_env = "base"` in a higher one, the higher layer's
  `conda_env` drops the lower `conda`, so `cfg['conda']` changes from `'x'` to `KeyError` for a user
  who reads only by item. That pair is already ambiguous on attribute access today, and it is part
  of the collision class the maintainer ruled undefined behaviour (resolved 2026-11-11; R1).
- **C3 · Q:** Two in-place changes that set different variants of one name
  (`cfg.update(token='a')`, then `cfg.update(token_env='X')`) leave both in `_` today, and attribute
  access raises. Do both stay? — **A:** No. A later in-place change replaces the earlier variant, in
  `_` and in the merged view, within `Configuration` only; plain `Namespace.update` is unchanged
  (resolved 2026-11-11; R5).
- **C4 · Q:** Today `cfg.token = 'v'`, when the merged view holds `token_env` but not `token`, sets
  an ordinary Python attribute. Is it an in-place change? — **A:** Yes. Top-level attribute
  assignment of a name whose variant is in the merged view is an in-place change under R5, with or
  without a collision (resolved 2026-11-11; R5).
- **C5 · Q:** What does "higher" mean, given that the merged view applies layers in the order they
  arrive while `which` puts `_` last? — **A:** `which`'s precedence: the layers in the order added,
  then `_`. The disagreement once a layer is added after an in-place change is a non-goal, recorded
  as `issues/configuration-layer-order.md` (resolved 2026-11-11; Outcome, Non-goals).
- **C6 · Q:** When the known-limitation line leaves § Invariants 2 (a human-gate section), does a
  line stating the rule take its place? — **A:** Yes: "`name`, `name_env` and `name_eval` are one
  key across layers: the highest layer that sets any of them decides" (resolved 2026-11-11; R8).

Raised during planning, ruled at the plan sign-off (2026-11-11):

- **C7 · Q:** A key such as `token_env` is a variant of `token` by its suffix and also a name with
  variants of its own (`token_env_env`, `token_env_eval`). In a chain of layers `token` →
  `token_env` → `token_env_eval` (low to high), R1 read for the name `token` keeps `token_env`, and
  R1 read for the name `token_env` drops it. Which reading holds? — **A:** The literal one: the
  highest layer that sets any key in the chain decides. Only `token_env_eval` survives, and
  `cfg.token` raises "'token' not found". This is the suffix rule (C2) applied to degenerate names,
  and it is accepted; `TestVariantCollision.test_double_suffix` pins it (resolved 2026-11-11; R1).
- **C8 · Q:** `_` folds in-place changes (C3), so in two in-place sequences no source still shows
  the variant that displaced a key: an in-place `a_env` over a layer's `a`, then an in-place
  `a_env_eval`; and a variant displaced in place, then set again fresh in place, with a key the fresh
  value lacks. There `which` names the layer that held the key while item access raises
  `KeyError`. Must `which` agree with item access there? — **A:** No, not in this cycle. `which`
  keeps today's answer in those two sequences: they are the same class as item assignment and `del`
  bypassing `_` (a non-goal), and are recorded with a test that shows them in
  `issues/config-local-layer-tracking.md` (resolved 2026-11-11; R3, R5).
  - 2026-11-11 (ruled on review cycle 2): C8 extends to two more sequences of the same class,
    where `_` folds in-place changes and loses the one that displaced or held a key, accepted for
    this cycle. **Shape C:** `Configuration(l={'s': 0})`, then `update(s={'t': 1})`, then
    `update(s={'t_env': 'X'})`: item access along `s`, `t` raises `KeyError`, and
    `which('s', 't')` raises `TypeError` from the layer's scalar. **The mirrored form of the first
    sequence:** `Configuration(l={'a_env_eval': 1})`, then `update(a_env='X')`, then
    `update(a='v')`: item access for `a_env_eval` raises `KeyError`, and `which('a_env_eval')`
    names `l`. Both are recorded, each with a test that shows it, in
    `issues/config-local-layer-tracking.md`.

## Related materials

- Seed: `issues/config-variant-collision.md`; `ROADMAP.md` Part II, order 3.
- Files: `src/cmdkit/namespace.py` (lines 56-103: assignment, the depth-first update, attribute
  expansion); `src/cmdkit/config.py` (lines 76-94 `extend`, 150-192 `which`, 232-272 `__setattr__`
  and `update`); `tests/test_config.py` (`TestNamespace` and `TestConfiguration`
  `test_attribute_expand_multiple_variants`, lines 288-293 and 518-528); `docs/index.rst` lines
  86-96; `AGENTS.md` § Invariants 1 and 2.
- Seeds that wait on or border this one: `issues/namespace-file-loading.md`,
  `issues/config-local-layer-tracking.md`, `issues/environ-mapping.md`,
  `issues/config-provenance.md`, `issues/config-explicit-expansion.md`,
  `issues/configuration-layer-order.md`.
- HyperShell's server `auth` key, the consumer case that invites the collision.
