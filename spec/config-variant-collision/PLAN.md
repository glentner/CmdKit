# PLAN — A value and its `_env` and `_eval` variants are one key across layers

> **Status:** Draft for review · **Last updated:** 2026-11-11
> **Authoritative technical design.** The *how*. Vision/contract is [`GOAL.md`](GOAL.md);
> the phased executable roadmap is [`TECH.md`](TECH.md). Backing detail is in
> [`research/`](research/) (two briefs: the change touches a high-blast-radius path). Every design
> element traces to a GOAL R-ID.

## 1. Summary

`Configuration` applies each layer, and each in-place change, through one private helper that
first prunes the target of every variant the incoming mapping displaces, then runs the existing
depth-first update unchanged. `which` gains a guard in front of its unchanged walk: when the merged
view lacks the path because a higher source set another variant on it, it raises `KeyError`.
Top-level attribute assignment counts a name as present when any variant of it is. Everything
lives in `src/cmdkit/config.py`; `namespace.py` is not touched, so plain `Namespace` behaviour
cannot move. Two phases: the layers (with the rule's docs and the `AGENTS.md` line), then in-place
changes. The gate drives the base and the branch side by side in fresh interpreters, checks a
collision corpus against an independent model of the rule, and runs a mutant sweep over every
decision the cycle adds, which `tests/test_config.py` alone must kill.

## 2. Design

### 2.1 Variants and siblings (`src/cmdkit/config.py`, module level)

A private helper gives the *siblings* of a key: the other keys that are a variant of a name the key
is a variant of. A key that is not a string has none. For a string `k`, the names it is a variant
of are `k` itself, `k` without a trailing `_env`, and `k` without a trailing `_eval` (GOAL's
definition, by suffix alone, C2); the siblings are every `n`, `n_env`, `n_eval` for those names,
`k` excepted. So `token_env` has siblings `token`, `token_eval`, `token_env_env` and
`token_env_eval`: it is a variant of `token` by its suffix and of `token_env` as itself. This is
GOAL's definition read literally, and the only place the suffixes are spelled.

### 2.2 Applying a mapping (R1, R4, R5, R6)

A private helper `_apply_layer(target, new)`:

1. **Prune.** For each key of `new`, delete from `target` every sibling that `new` does not set
   itself; then, where the key's value is a `dict` in both `new` and `target`, recurse into that
   pair. The recursion test is the depth-first update's own (`isinstance(…, dict)` on both sides),
   so the prune acts at exactly the levels the merge will descend to, and nowhere else. Above a
   level where the merge replaces, the lower values go wholesale anyway.
2. **Merge.** `NSCoreMixin.update(target, new)`: the existing depth-first update, reused, not copied.

The prune only deletes from `target`'s own mappings. Those are always fresh copies
(`NSCoreMixin.__setitem__` stores every mapping through `_as_namespace`), so neither a layer nor the
caller's argument is ever touched (R6). It uses `in` and `del` only, so nothing expands (R6,
§ Invariants 2). When `new` sets two variants of one name, both survive and attribute access raises
as today (R4); a key `new` sets is never pruned, so a mapping-valued variant set again by a higher
layer still merges depth-first with the lower one (R7).

Callers:

- `Configuration.extend`: `_apply_layer(self, self.namespaces[name])` in place of
  `super().update(...)`. `extend(_=m)`, which `Configuration(_=...)` reaches, keeps
  `self.local.update(m)` (a non-goal).
- `Configuration.update` (P2): `_apply_layer(self.local, dict(*args, **kwargs))`, then
  `_apply_layer(self, dict(*args, **kwargs))`. Building the argument once per side, as today, keeps
  a one-shot iterable of pairs reaching `_` only (research 01; R7). Applying the rule to `_` as well
  is what makes a later in-place variant replace an earlier one there (C3).

### 2.3 Attribute assignment (R5, C4; P2)

`Configuration.__setattr__` treats `name` as a parameter when `name in self` *or* any sibling of
`name` is in the merged view, and then calls `self.update({name: value})`; otherwise it sets an
instance attribute as today. `__init__` sets `local` and `namespaces` while the merged view is
empty, so it is unaffected.

### 2.4 `which` (R3)

The walk stays as it is, byte for byte. In front of it:

```
if <item access along path raises KeyError in the merged view>
   and <above a source that holds all of path, some source, at the place of a key on path,
        holds a sibling of that key and not the key itself>:
    raise KeyError(f'Not found: {path}')
```

- "Sources" are the layers in the order added, then `_`: `which`'s own precedence (C5).
- "Item access raises `KeyError`": walking the merged view, a mapping on the way lacks the next
  key. A step through a value that is not a mapping is *not* this case, so `which` keeps raising
  `TypeError` there as today (research 02).
- The displacement is looked for at every depth of the path, not only where the merged view lacks
  a key: a section dropped as a whole and set again fresh higher up lacks a deeper key (research 02).
- Both conditions are needed (research 02): without the first, a variant set again by a higher
  layer would raise instead of naming that layer; without the second, the non-goal paths that
  already make `which` and the merged view disagree (item assignment, `del`,
  `Configuration(_=...)`, a layer added after an in-place change) would change answer.

So in R1's case `which` names the upper layer for the upper variant (the walk finds it first) and
raises `KeyError` for a lower one's key; a bare name whose only variants are suffixed raises
`KeyError` as today (no source holds it literally); after an in-place change `which` names `_` for
the new variant (R5). Three private helpers carry it: a lookup that returns a sentinel for a missing
path, the merged-view test, and the displacement test.

### 2.5 Documentation (R8)

Same commit as the layers' code (P1), per § Conventions:

- the `Configuration` class docstring states the rule in a sentence or two and shows it in an
  `Example:` block (two layers, `password` and `password_eval`; `dict()`, attribute access,
  `which`);
- `docs/index.rst`, in the passage that introduces `_env` and `_eval` (after "Accessing the
  parameter with dot-notation …"), a short paragraph stating the rule;
- `AGENTS.md` § Invariants 2: the known-limitation line for the collision is replaced, in place, by
  "- `name`, `name_env` and `name_eval` are one key across layers: the highest layer that sets any
  of them decides." (C6). No other line of `AGENTS.md` changes.

P2 adds a sentence to the `Configuration.update` docstring's Note: an in-place change follows the
same rule, in `_` and in the merged view. `docs/api/config.rst` documents both through
`autoclass`/`automethod`, so no page under `docs/api/` needs its own edit.

### 2.6 Tests (`tests/test_config.py`)

`TestConfiguration.test_attribute_expand_multiple_variants` keeps its `Configuration(...)` and
asserts, outside any `pytest.raises`, `cfg.nested.a == 1`, `cfg.nested.b == 2`,
`cfg.other.secret == 'baz'` and `cfg.nested.test == 'bar'` (R7). Every other test collected at the
base stays as it is. A new class `TestVariantCollision` holds the rest, by the names TECH.md gives
(the gate looks for them): the six ordered pairs, the top level, three levels deep, the suffix-only
key (C2), mapping values, the deciding layer's own ambiguity (R4), plain `Namespace.update`
unchanged, no expansion (an `_eval` that would `touch` a file under `tmp_path`, `os.getenv`
monkeypatched to record calls), keys that are not strings, the double suffix, `which` neighbours
(through scalars, missing keys, a variant set again higher up, a variant displaced past a scalar);
and at P2 `update`, successive updates, attribute assignment (from one layer, from a collision, a
suffixed name) and unchanged attribute assignment.

### Requirement → design map

| R-ID | Design element(s) that satisfy it |
|------|-----------------------------------|
| R1   | § 2.1 siblings, § 2.2 prune in `extend`. Shown by `test_pairs`, `test_top_level`, `test_deep`, `test_suffix_alone`, `test_mapping_values`; the drive's `model` corpus. |
| R2   | § 2.2 (the merged view holds one variant, so the unchanged `__getattr__` expands it, and item access reads it). `test_pairs` (variable set by `monkeypatch`, `echo` for `_eval`); the `model` corpus's attribute and item checks. |
| R3   | § 2.4. `test_pairs`, `test_top_level`, `test_deep`, `test_suffix_alone`, `test_mapping_values`, `test_which_restored`, `test_which_displaced_through_scalar`; the `model` corpus. |
| R4   | § 2.2 (a key `new` sets is never pruned). `test_deciding_layer_ambiguous`, `test_namespace_update_unchanged`, the unchanged `TestNamespace.test_attribute_expand_multiple_variants`. |
| R5   | § 2.2 `update` on `_` and the merged view, § 2.3. `test_update`, `test_successive_updates`, `test_attribute_assignment`; the `model` corpus at P2. |
| R6   | § 2.2 (prune touches only fresh copies; `in` and `del` only). `test_no_expansion`, the layer checks in `test_pairs` and P2's tests; the `model` corpus's layer and spy checks. |
| R7   | `namespace.py` untouched; the walk and the depth-first update reused unchanged; `update`'s argument built per side. The changed test; every base node ID passing; the drive's `same` corpus against the base; `test_which_unchanged`, `test_which_through_scalars`, `test_non_string_keys`, `test_attribute_assignment_unchanged`. |
| R8   | § 2.5. `change_set.py` checks 3–5 (the rule line, the docs, one commit); the wording is the review's to grade. |

## 3. Invariant gate (AGENTS.md constitution check)

Walked before research and again against this design. Sections touched: § Invariants 1 and 2
(human gates), the high-blast-radius list (`src/cmdkit/config.py`), § Conventions.

- **High-blast-radius paths.** Touches `src/cmdkit/config.py` only, so research ran (trigger 2).
  `src/cmdkit/namespace.py` is on the list too and stays byte for byte (`change_set.py` check 2).
- **§ 1 Compatibility.** GOAL calls the collision an outright failure and names the test that pinned
  it, so the fix is the default with no opt-in, as § 1 directs. Lazy expansion, `which` returning a
  label, and every `__all__` name are unchanged; nothing new is public.
- **§ 2 Configuration core.** Loading, construction, merging, item access and `dict()` still never
  expand (the prune uses `in` and `del`; `test_no_expansion`; the drive's spies). A layer is still
  copied in, and the prune never reaches one. The merge is still depth-first, and the prune descends
  exactly where it does. In-place changes are still recorded in `_`, and `which` names `_` for them.
  The known-limitation line for the collision is replaced by the rule line, as R8 and C6 direct; the
  `_`-bypass limitation line stays.
- **§ 4 Footprint.** No dependency, no import-time effect, the 3.9 floor holds (the code and the
  gate scripts run on 3.9).
- **§ Conventions.** Code and docs in one commit per phase; no spec ids in source, tests or docs
  (`change_set.py` check 6); SPDX blocks and import groups untouched; the new helpers carry
  docstrings and annotations.

### Deviation justifications

| Deviation | Why needed | Simpler alternative rejected because |
|-----------|-----------|--------------------------------------|
| Reading: `cfg.token_env = v` (a suffixed name) over a merged view holding `token` is an in-place change, so `_` records `token_env` and the merged view drops `token`. | R5's first sentence covers "attribute assignment of a parameter" that sets a variant where the merged view holds a different one; C4 names the plain-name case. The sibling test in § 2.3 gives both. | Testing only `name`, `name_env`, `name_eval` of the assigned name would set an instance attribute for `cfg.token_env = v`, leaving the merged view's `token` in force and `_` empty: the failure C4 rules out, for the other direction. |
| Reading (**needs the maintainer's ruling at sign-off**): after in-place changes collapse a displacement out of `_`, `which` beneath it keeps today's answer. Two shapes: `a` displaced by an in-place `a_env`, then `a_env` replaced by an in-place `a_env_eval` (C3); and a variant displaced by an in-place change, then set again fresh by another, with a key the fresh value lacks. `which` names the layer that held the key, while item access raises `KeyError`. | `_` folds in-place changes (C3 requires it), so the displacing variant is gone from every source; the state is identical to one reached through `del` (a non-goal), where R7 requires today's answer. Today's `which` already names a layer beneath any value an in-place change replaced. R3's agreement holds in every case GOAL shows (two layers; an in-place change over a layer; successive in-place changes of `name` and `name_env`). | A relation by root (strip every suffix) catches the first shape but changes `which` after `del` or item assignment beside an unrelated `a_env_eval`, outside any collision (R7). Recording displaced paths on the `Configuration` adds state that shows in `vars()`, copies and pickles of every configuration. Either is a maintainer's call; the plan keeps R7 exact. |
| Reading: `token_env` is a variant of two names, `token` (by suffix) and `token_env` (as itself), so a higher `token_env_eval` displaces a lower `token_env`, and a higher `token_env` displaces a lower `token_env_eval`. Consequence in a three-layer chain `token`, `token_env`, `token_env_eval` (low to high): only `token_env_eval` remains, so `cfg.token` raises "'token' not found" although the middle layer set `token_env`. R1 read for the name `token` (deciding layer: the middle one) wants `token_env` kept; R1 read for the name `token_env` (deciding layer: the top one) wants it gone. No design meets both; the plan lets the higher layer's rule win. | GOAL's definition read literally ("any of the keys `name`, `name_env` and `name_eval`"; "a variant by its suffix alone"). Attribute access already treats `cfg.token_env` as having variants `token_env_env` and `token_env_eval`. In the chain, keeping `token_env` would leave two variants of `token_env` across layers, the collision this cycle removes. | Treating only the suffix-stripped name would let `token_env` and `token_env_eval` from different layers both survive, and `cfg.token_env` raise "more than one variant", one level up. `test_double_suffix` pins the reading, the chain included. **Needs the maintainer's ruling at sign-off.** |
| A second mapping walk beside the depth-first update (the prune), and three private helpers for `which`. | The rule needs the incoming mapping's whole key set at each level before anything is assigned; `which` needs the merged view and the sources together. | Adding a flag to `NSCoreMixin.__depth_first_update` would put the rule in `namespace.py` (high blast radius) and in the update plain `Namespace` uses (a non-goal); copying the update into `config.py` would restate the depth-first rule in a second place. The prune reuses it. |

## 4. Rabbit holes (resolved)

- **Where the merge happens, and whether pruning can reach a layer** → every stored mapping is a
  fresh copy; the prune runs on the merged view and `_` only
  ([`research/01-merge-and-layers.md`](research/01-merge-and-layers.md)).
- **`which` without reading the merged view** → it is right whenever the merged view holds the
  path; a guard decides the displaced case and the walk stays
  ([`research/02-which.md`](research/02-which.md)). Two earlier drafts of the guard failed the
  drive: one consulted only the source walk (missed a section dropped and set again fresh); one
  looked only at the depth where the merged view lacks a key (same miss, other way round).
- **`update`'s one-shot iterable** → kept as today by building the argument per side (research 01).
  It parts `_` from the merged view (today's behaviour), so the drive's model does not grade `which`
  beneath the keys such an update sets.
- **Equivalent mutants** → a function's closing `return False` is not deleted by the sweep
  (deleting it returns `None`, which no boolean caller tells apart); its `False` is still flipped.
  No other exclusion: the prototype's sweep kills every mutant.
- **Adversarial review** → see § 7.

## 5. Risks & open questions

- **The `_`-collapse reading** (§ 3, second row) is the one place `which` and item access may
  disagree after variant changes. It needs a chain of in-place changes; no layer-only configuration
  reaches it. If the maintainer prefers the root relation or recorded state, it is a small change to
  the guard's relation, and the drive's `same` corpus would then show the `del` difference.
- **`which` with an unhashable path key** raises `TypeError` from the guard's merged-view test
  rather than from the walk; both say "unhashable type", and the drive pins the message on both
  Pythons.
- **Hypothesis and the corpus seeds.** The drive's corpora are seeded (`random.Random(seed)`), so a
  run is reproducible; the mutant sweep runs only `tests/test_config.py`, which uses no Hypothesis
  strategy.
- **Gate time** is about 3 to 4 minutes per phase on the planning host (measured, § 6); within
  build's budget, and every mode can run alone.
- **The gate trusts the repository for its own freeze.** `frozen` finds the plan commit by subject
  and refuses verify/ or PLAN.md changes after it, and any work outside `spec/`, `issues/` and
  `ROADMAP.md` before it; a history rewritten below the plan commit is beyond any in-repo check. The
  plan commit's hash and the frozen tree id are reported outside the repository, so the review can
  run `git rev-parse <plan>:spec/config-variant-collision/verify` against them and run the gate from
  that tree.

## 6. Verification strategy

Frozen gate tree: `3bf496f8c697868033f2ac550c9ba439df79912c`

The gate is `sh spec/config-variant-collision/verify/gate.sh MODE [PHASE]`; its header lists the
modes. It reads the index (stage the phase first), never the working copy, and refuses to run when
`verify/` or this file differs from the plan commit, when a build commit precedes the plan commit,
or when `verify/`'s tree at HEAD is not the tree recorded above.

- **`static`**: `change_set.py` (files since the plan commit; `src/` outside `config.py` byte for byte
  the base's; the `AGENTS.md` line replaced in place and alone; the docs passage and the class
  docstring, and at P2 the `update` docstring; code (docstrings aside) and docs first change in the
  same commit; no spec ids in added lines; at P2 the deferral ledger, quoted text not read as a
  deferral) and `tests_kept.py ast` (every base test kept by syntax tree, nothing added to a base
  class, the module gaining only imports, plain new names and `TestVariantCollision` with plain
  test functions, nothing that pins the source; the changed test's body exactly as TECH.md gives
  it; the phase's named tests present).
- **`suite`**: the profile's `verify` on 3.9 and 3.14 from an export of the index, then
  `tests_kept.py passed`: every one of the 75 base node IDs and every named test PASSED, six
  `test_pairs` cases, nothing failed or skipped. Then the base's own `tests/test_config.py`, with
  only the changed test's body rewritten as GOAL words it, runs against the index's `src/` on both
  Pythons and all 35 of its tests pass: R7's "unchanged", literally.
- **`drive`**: `drive.py` on 3.9 and 3.14, base and branch each in a fresh interpreter under spies
  on `os.getenv` and `subprocess.check_output`. `same` (10 fixed scenarios, 400 seeded ones, 3 plain
  `Namespace` ones): every record identical to the base's, including `which` through scalars, item
  assignment, `del`, `Configuration(_=...)`, a layer after an in-place change and the one-shot
  iterable. `model` (400 seeded collision scenarios; layers through the constructor and through
  `extend`, one or two at a time; at P2 `update` with a mapping, keywords or a one-shot iterable,
  and attribute assignment): no problem on the branch, and at least half fail on the base. `which`
  is graded strictly everywhere except beneath a key an in-place change dropped or replaced
  wholesale (today's staleness, § 3 second row) and beneath the keys of a one-shot iterable.
- **`mutants`**: `mutants.py` on 3.14 over the lines the cycle adds to `src/cmdkit/config.py`
  (an expression by every line it spans, a compound statement by its first line; function bodies
  and module-level assignments). Operators: negated tests, `and`/`or` swaps and dropped operands,
  swapped comparisons, dropped `not`, statements to `pass`, `_env`/`_eval` swaps, integers and
  slice bounds by one, `True`/`False`, `any`/`all`, `break`/`continue`, `reversed` to `list`, and
  the first two arguments of a private helper swapped. Decisions it mutates (on the prototype: 107
  mutants at P1, 119 at P2):
  - the sibling helper: the string-key guard, each suffix test and slice length, the `!= key`
    filter, the suffix strings;
  - the prune: the sibling-present-and-not-set test (each operand, each operator), the deletion, the
    descent test (each operand), the recursion;
  - the helper's two steps (prune, update) and each call site (`extend`; at P2 both sides of
    `update`);
  - the `which` guard: each of its two conditions, the merged-view walk (mapping test, missing-key
    test, descent, each return value), the displacement test (held, mapping parent, key absent,
    sibling present, the `held` update), the sentinel lookup;
  - at P2, attribute assignment's two conditions.
  Each must make `tests/test_config.py` fail. Measured on the prototype: P1 88 s, P2 99 s.
- **`P1`**, **`P2`**: `static`, `suite`, `drive`, `mutants` for the phase. Measured on the
  prototype, each phase's gate on its own phase's tree: P1 167 s, P2 over 180 s; and each refuses
  the tree before it (P1 on the plan commit: every static check red; P2 on the P1 tree: the four P2
  tests missing, 259 of 400 model scenarios failing).
  **`prepush`**: `static P2` and `suite P2`.

## 7. Adversarial design review

One fresh reviewer ran against `GOAL.md`, this design, the drafted gates and the prototype, and
attacked the prototype in a throwaway worktree of its own. Its findings, and what changed:

1. **HIGH — the gate passed a build that ignores the rule in `extend()` after construction**
   (`from_local`'s real path): the model built layers only through the constructor. Now the model
   corpus adds layers through `extend`, one or two at a time, and at P2 updates with keywords and
   with a one-shot iterable too; TECH names `test_extend_and_from_local` (two TOML files under
   `tmp_path`). The drive now fails that build (208 of 400 model scenarios).
2. **HIGH — a base test could be replaced without touching its syntax tree** (a module-level
   `TestConfiguration.test_blending = lambda self: None`), or shadowed by an autouse fixture.
   Now `tests_kept.py ast` admits only imports, plain new names and `TestVariantCollision` with
   plain test functions, refuses new members in base classes and source-pinning names, and `suite`
   runs the base's own `tests/test_config.py` (the one test rewritten as GOAL words it) against the
   branch's `src/`.
3. **MEDIUM — a docstring-only commit counted as the code's first change**, so docs could land one
   commit ahead of the code. Check 5 now compares syntax trees with docstrings removed.
4. **MEDIUM — `frozen` trusted build-commit subjects.** It now refuses a plan commit after any
   commit that changes files outside `spec/`, `issues/` and `ROADMAP.md`, whatever its subject; the
   plan hash and the tree id go out of band (§ 5).
5. **MEDIUM — mutant blind spots.** The sweep now mutates by span, covers module-level
   assignments, slice bounds, `reversed`, and the argument order of private helpers; `tests_kept.py`
   refuses tests that read the source; TECH forbids unreachable defensive statements.
6. **MEDIUM — the double-suffix chain** (`token`, `token_env`, `token_env_eval`) loses `token`
   entirely. Recorded in § 3's third row for the maintainer's ruling, and pinned in
   `test_double_suffix`.
7. **MEDIUM — the `_`-collapse reading** needs an explicit ruling, and the drive excused every
   `which` after any in-place change. § 3's second row is flagged for sign-off, and the drive now
   excuses `which` only beneath a key an in-place change dropped or replaced wholesale.
8. **LOW — the docs checks are loose.** TECH now says the gate finds the docs and the review grades
   their words; P2 checks the `update` docstring too.
9. **LOW — the ledger read quoted text** (it flagged a quoted `AGENTS.md` line). Quoted and
   backticked text is no longer read as a deferral.

---

*Backing research: [`research/00-digest.md`](research/00-digest.md).*
