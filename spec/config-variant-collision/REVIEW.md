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
