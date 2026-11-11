# REVIEW — A value and its `_env` and `_eval` variants are one key across layers

> Adversarial QA by `code-review`, run in an isolated/clean context (a subagent; where the runtime
> has none, `code-review`'s sequential fallback). The correctness pass grades the branch diff against
> [`GOAL.md`](GOAL.md) + the repo's `AGENTS.md` § Invariants **only** — it does not see
> `PLAN.md`/`TECH.md` (avoids grading-its-own-homework / plan-sycophancy). Every finding cites an
> **executed** command, not an assertion.

- **Reviewed commit:** 6f13c3622dcdd0adc4ec7e1526c767085820c2ec  ·  **Base:** develop  ·  **Date:** 2026-11-11
- **Verdict:** changes-requested
- **Cycle:** 1 of ≤3. Mirrors `review.cycle` in `TECH.md`.

A single fresh reviewer, blind to `spec/`. The GOAL commits after the shape commit are the
clarifications C1–C8, ruled at the GOAL and PLAN gates before the build.

## Verification run

- **The profile's `verify`,** sandboxed: 99 passed on Python 3.9.25 and 99 on 3.14.6.
- **Test merge with develop:** the branch merges cleanly into `origin/develop`, and `verify` on the
  merged tree passes 154 tests on each Python.
- **Probes** in fresh `python -I` processes against HEAD and base: every ordered pair of variants
  across two layers, three-layer permutations, top-level and four-deep paths, mapping against
  scalar, section displacement, the suffix case (C2), the double-suffix chain (C7), within-layer
  ambiguity (R4), in-place changes (C3, C4), and HyperShell's `auth` with `auth_eval` / `auth_env`,
  including through TOML files.
- **An independent rule model** fuzzed 15,000 random stacks of layers (205,275 paths), and 15,000
  stacks with one update (252,548 paths). Neither run shows a single mismatch in the merged view or
  `which`. Mismatches with two updates all come from `_` folding (C8).
- **R6:** no layer is mutated, and no `_env` is read or `_eval` run outside attribute access. Both
  were checked with spies, with a positive control.
- **R7:** the plain and `from_local` scenario sets are byte-identical on HEAD and base. The base's
  suite run against HEAD fails exactly the one test whose expectation changed.
- **Mutation sweep:** 33 mutants, 31 killed. M03 and M11 survive, and both are equivalent by
  reasoning and by the model.
- **The docs:** Sphinx builds with 0 warnings.

## Requirement → evidence matrix

| R-ID | Implemented by | Verified how | Status |
|------|----------------|--------------|--------|
| R1 | `config.py` (747ea90) | pairs, three layers, depth, mapping and scalar, sections, C2, C7 | ✅ |
| R2 | `config.py` (747ea90) | attribute and item access across all six pairs | ✅ |
| R3 | `config.py` (747ea90) | surviving and dropped keys, bare names (C1), the model fuzz. **F1:** a path no layer holds, through a displaced scalar | ❌ |
| R4 | `config.py` (747ea90) | within-layer ambiguity; `Namespace` unchanged | ✅ |
| R5 | `config.py` (6f13c36) | `update`, successive updates (C3), attribute assignment (C4), unchanged cases | ✅ |
| R6 | `config.py` | deep-copy comparisons; spies with a positive control | ✅ |
| R7 | — | byte-identical scenario sets; the base suite on HEAD; C5 and C8 reproduce | ✅ |
| R8 | docstring, `docs/index.rst`, `AGENTS.md` (747ea90) | same commit; C6 verbatim; the examples run; Sphinx clean | ✅ |

**Unmapped changes:** `issues/configuration-layer-order.md`, the note in
`issues/config-local-layer-tracking.md`, and their `ROADMAP.md` entries. They are accurate deferral
records.

## Findings

### [LOW/CONFIRMED] F1 · `which` and item access disagree on a path that runs through a displaced scalar
- **Where:** `src/cmdkit/config.py:102` (`_displaced`'s `held`) and `:271-282` (`which`).
- **Failure scenario:** layers `lower={'u': 0}` and `upper={'u_env': 'X'}`, with path `('u','t')`.
  Item access raises `KeyError: 'u'`, but `which` raises `TypeError`. Base raises `TypeError` for
  both. Likewise for `('s','token','a')` over `{'s': {'token': 5}}` and `{'s': {'token_env': 'X'}}`.
- **Evidence:** `r3edge.py`.
- **Touches:** R3 and C1 (`which` agrees with item access). This is a high-blast-radius path.

### [LOW/CONFIRMED, out of Scope] F2 · `BuilderConfiguration.trim` crashes on a section displaced by a variant
- **Where:** `src/cmdkit/contrib/builder.py:149-163`. The file is untouched.
- **Failure scenario:** layers `one={'s':{'x':1}}`, `two={'s':{'x':2}}` and `three={'s_env':'V'}`.
  `trim()` raises `KeyError 's'`.
- **Evidence:** `trim.py`.
- **Out of Scope:** the input is in the collision class ruled undefined behaviour, and base already
  crashes on the structural analogue. It is filed to the `builder-trim-local-layer` seed.

## Human-gate triggers

- F1 is CONFIRMED in `src/cmdkit/config.py`, a high-blast-radius path, so the maintainer's ruling is
  required.

## Maintainer's ruling on review cycle 1 (2026-11-11)

- **F1: fix it first.** Remediate in P1, then run a scoped review cycle 2 that verifies only the
  fix, then the PR. The property to restore: `which` agrees with item access (R3, C1) for every
  path, including one that no layer holds and that runs through a displaced scalar.
- **F2:** out of Scope. It goes to the `builder-trim-local-layer` seed in the next roadmap upkeep
  PR, because this cycle's frozen gate admits no `issues/` edit after the plan.

## Review cycle 2 (scoped to F1 and the 2.8.0 release materials) — changes-requested (2026-11-11)

**Reviewed commit:** 46e3f8729f2b3db71f80fa325d4a1632ca34e84f.

### Verification run
- **F1 is remediated** for every stack of layers. Both of the review's examples now give `KeyError`
  from item access and from `which`, on 3.9 and 3.14.
- **Fuzz:** 12,000 stacks and 1,475,109 path queries. Every disagreement between `which` and item
  access is one of:
  - 2.7.7's own no-displacement `TypeError` (pinned against `cmdkit==2.7.7`);
  - a pre-existing case with no variant involved (out of Scope);
  - one of C8's two shapes;
  - shape C below (5 queries).
- **Regression check:** 3,000 stacks compared with `6f13c36`. The merged view, `_`, attributes,
  attribute-access results and item-access results are identical. `which` differs only where item
  access raises `KeyError`.
- **Mutation sweep:** 18 mutants on copies, 16 killed. One survivor is equivalent; the other is F5.
- **Release materials:** every factual claim was executed against HEAD and `cmdkit==2.7.7`, the
  code example verbatim. Hygiene is clean. The docs build passes `sphinx-build -E -W`.
- **The profile's `verify`:** 155 passed on 3.9 and 155 on 3.14.

### Findings
- **[MEDIUM/CONFIRMED] F1 (shape C):** `Configuration(l={'s': 0}); update(s={'t': 1});
  update(s={'t_env': 'X'})` gives item access `KeyError` but `which` `TypeError`. The cause is the
  same as C8's: `_` folds the in-place changes and loses the one that held the key. It is not a
  regression from `6f13c36`. Location: `src/cmdkit/config.py:99-112, 280`.
- **[LOW/CONFIRMED] F2:** the release note defines "higher" without the extend-after-update caveat
  (C5).
- **[LOW/CONFIRMED] F3:** `docs/api/config.rst:45-48` states the `which` agreement with no in-place
  caveat.
- **[LOW/CONFIRMED] F4:** the release note's Project bullet promises specific features for 2.8.x.
- **[LOW/CONFIRMED] F5:** the mutant `depth in held` → `held` survives. The `TypeError` kept when a
  lower source holds only a shorter prefix is unpinned.
- **[LOW/PLAUSIBLE] F6:** "Nothing a consumer installs changes" reads as an absolute claim.

### Human-gate triggers
- F1 is CONFIRMED in `src/cmdkit/config.py`, a high-blast-radius path.

## Maintainer's ruling on review cycle 2 (2026-11-11)

**Extend C8, then ship.**
- Shape C joins C8 as a third accepted `_`-folding shape, together with the mirrored form of
  shape (1). All of them go to the `config-local-layer-tracking` seed for 2.8.x.
- F2, F3, F4 and F6 are fixed in the docs.
- F5 gets a pinning test.
- A short scoped verification follows, then the PR.
