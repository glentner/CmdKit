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
`_` (but see C5).

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
- **R3** — In R1's case, `cfg.which(*path, key)` SHALL name the higher layer for the key of the
  variant that is in the merged view. Today it names whichever layer last set that literal key, so
  it can name a layer whose value the merged view should not hold.
  `[NEEDS CLARIFICATION: C1 — what does which return for the key of a variant that is no longer in
  the merged view, and for the bare name when only a variant is present?]`
- **R4** — IF the deciding layer itself sets two or more variants of `name` at one path, THEN the
  merged view SHALL hold those variants (and no lower layer's), and attribute access SHALL raise
  `AttributeError` with "'name' has more than one variant", as today. A single `Namespace` holding two
  variants keeps today's behaviour in full: `TestNamespace.test_attribute_expand_multiple_variants`
  keeps its expectation.
- **R5** — WHEN an in-place change (`Configuration.update`, or attribute assignment of a parameter)
  sets a variant of `name` at a path where the merged view holds a different variant, the change
  SHALL be recorded in `_`, the merged view SHALL hold only the new variant, attribute access and
  item access SHALL agree with it as in R2, and `which` SHALL name `_`.
  `[NEEDS CLARIFICATION: C3 — successive in-place changes that set different variants]`
  `[NEEDS CLARIFICATION: C4 — top-level attribute assignment of a bare name whose variant is in the
  merged view]`
- **R6** — No layer in `Configuration.namespaces` SHALL be modified by construction, `extend`,
  `update`, attribute assignment or attribute access: after any of them, each layer still equals the
  mapping it was built from. Loading, construction, merging, item access and `dict()` SHALL still
  never read an `_env` variable or run an `_eval` command (§ Invariants 2).
- **R7** — Everything outside a variant collision SHALL behave as today: the depth-first merge of one
  key set by several layers, plain `Namespace` updates and attribute access, `which` for keys no
  collision touches, and `whereis` and `duplicates`. Every test collected from `tests/` at `38ff951`
  SHALL still pass unchanged except `TestConfiguration.test_attribute_expand_multiple_variants`.
  That test (layer `a` sets `nested.test`, layer `b` sets `nested.test_eval = 'echo bar'`) SHALL
  instead expect `cfg.nested.test == 'bar'`, with `cfg.nested.a == 1`, `cfg.nested.b == 2` and
  `cfg.other.secret == 'baz'` still holding, and no `AttributeError`.
- **R8** — The documentation SHALL state the rule, in the same commit as the code (§ Conventions):
  the `Configuration` docstring and the passage of `docs/index.rst` that introduces `_env` and
  `_eval`. `AGENTS.md` § Invariants 2 SHALL no longer list the collision as a known limitation.
  `[NEEDS CLARIFICATION: C6 — does § Invariants 2 gain a line stating the rule in its place?]`

**How it is shown.**

1. For each ordered pair of distinct variants of one name (six cases), a two-layer `Configuration`
   with the pair at `section.name`: the merged view holds only the upper variant (R1); attribute
   access returns the upper layer's value, with the variable set for `_env` and `echo` for `_eval`,
   and item access agrees (R2); `which` names the upper layer (R3); both layers still equal their
   inputs (R6). One case repeated at the top level and one three levels deep.
2. A lower layer with one variant under an upper layer with the other two: attribute access raises
   "has more than one variant" and the lower variant is absent (R4).
3. R5's in-place cases, through `update` and through attribute assignment.
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
  merged view while `which` names `_`. This predates the cycle and involves no variant; see C5.
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

Raised during shaping, open:

- **C1** `[NEEDS CLARIFICATION]` **Q:** In R1's case, what does `which` return for the key of a
  variant only a lower layer set (`which('hf', 'token')` when the upper layer set `token_env`), and
  for a bare name when the merged view holds only a variant of it (today `KeyError` even with no
  collision)? (a) `which` stays keyed on the literal key, answered from the merged view: `KeyError`
  for both, agreeing with item access; (b) `which` resolves a bare name the way attribute access
  does and names the layer of the variant present, for both.
- **C2** `[NEEDS CLARIFICATION]` **Q:** Does the rule apply to every key ending in `_env` or
  `_eval`, including one the user never meant as a variant (`conda = "x"` in one layer,
  `conda_env = "base"` in a higher one)? Under the rule the higher layer's `conda_env` would drop the
  lower `conda`, so `cfg['conda']` changes from `'x'` to `KeyError` for a user who reads only by
  item. (a) Yes, by suffix, as attribute access already treats such keys; (b) something narrower.
- **C3** `[NEEDS CLARIFICATION]` **Q:** Two in-place changes that set different variants of one name
  (`cfg.update(token='a')`, then `cfg.update(token_env='X')`) leave both in `_` today, and attribute
  access raises. (a) A later in-place change is higher than every earlier one, so the later variant
  replaces the earlier one in `_` and in the merged view; (b) `_` is one layer, so both stay and
  attribute access raises (R4).
- **C4** `[NEEDS CLARIFICATION]` **Q:** Today `cfg.token = 'v'`, when the merged view holds
  `token_env` but not `token`, sets an ordinary Python attribute: nothing reaches `_` or the merged
  view. After R1, the cross-layer case (`token` low, `token_env` high) lands there too. (a) Top-level
  attribute assignment of a bare name whose variant is in the merged view is an in-place change under
  R5, with or without a collision; (b) only where a collision made the bare name disappear;
  (c) neither: it stays as today.
- **C5** `[NEEDS CLARIFICATION]` **Q:** "Higher" is defined above as `which`'s precedence (layers in
  the order added, then `_`). The merged view instead applies layers in the order they arrive, so the
  two disagree once a layer is added after an in-place change. (a) Take `which`'s precedence for this
  rule, leave the existing disagreement as a non-goal, and record it as a new seed; (b) fix the
  disagreement in this cycle.
- **C6** `[NEEDS CLARIFICATION]` **Q:** When R8 removes the known-limitation line from § Invariants 2
  (a human-gate section), does a line stating the rule take its place? (a) Yes: "`name`, `name_env`
  and `name_eval` are one key across layers: the highest layer that sets any of them decides"; (b) no,
  remove only.

## Related materials

- Seed: `issues/config-variant-collision.md`; `ROADMAP.md` Part II, order 3.
- Files: `src/cmdkit/namespace.py` (lines 56-103: assignment, the depth-first update, attribute
  expansion); `src/cmdkit/config.py` (lines 76-94 `extend`, 150-192 `which`, 232-272 `__setattr__`
  and `update`); `tests/test_config.py` (`TestNamespace` and `TestConfiguration`
  `test_attribute_expand_multiple_variants`, lines 288-293 and 518-528); `docs/index.rst` lines
  86-96; `AGENTS.md` § Invariants 1 and 2.
- Seeds that wait on or border this one: `issues/namespace-file-loading.md`,
  `issues/config-local-layer-tracking.md`, `issues/environ-mapping.md`,
  `issues/config-provenance.md`, `issues/config-explicit-expansion.md`.
- HyperShell's server `auth` key, the consumer case that invites the collision.
