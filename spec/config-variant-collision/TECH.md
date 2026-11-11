---
slug: config-variant-collision
title: A value and its _env and _eval variants are one key across layers
kind: fix
appetite: small
status: blocked
branch: fix/config-variant-collision
base: develop
current_phase: done
last_updated: '2026-11-11'
phases:
- id: P1
  name: Layers decide variants, and which agrees
  status: done
  satisfies:
  - R1
  - R2
  - R3
  - R4
  - R6
  - R7
  - R8
  depends_on: []
  parallel: false
  hammerable: false
  hill: uphill
  attempts: 2
  verify: sh spec/config-variant-collision/verify/gate.sh P1
- id: P2
  name: In-place changes follow the rule
  status: done
  satisfies:
  - R5
  - R6
  - R7
  depends_on:
  - P1
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/config-variant-collision/verify/gate.sh P2
review:
  last_reviewed_commit: 46e3f8729f2b3db71f80fa325d4a1632ca34e84f
  verdict: changes-requested
  blocked_reason: 'review 2: extend C8 (shape C), docs F2-F4/F6, test F5'
  cycle: 2
---

# TECH.md — A value and its `_env` and `_eval` variants are one key across layers

The **context engine and finite-state machine** for building this fix. The YAML frontmatter above
is the resume ground-truth (read it from the cycle worktree with the factory's `next_phase.py`);
the per-phase checklists below are the work. The build step executes the next actionable phase,
runs its `verify:` command, updates state with the factory's `set_phase.py`, and makes one atomic
code+state commit.

- **Vision / requirements (locked):** [`GOAL.md`](GOAL.md) — R-IDs are the contract.
- **Authoritative design:** [`PLAN.md`](PLAN.md).
- **Backing research:** [`research/00-digest.md`](research/00-digest.md) and its two briefs.

## Frontmatter field reference

- `status` (top): `planned | in_progress | blocked | in_review | done` (`done` is stamped by
  the publish step after confirmation, just before landing — the terminal state of the retained record)
- `appetite`: `small | big` — caps phase count and build-iteration budget (circuit breaker).
- `branch`, `base`: the cycle's branch (prefix per GOAL `kind`, from the profile's `branches`) and the
  profile's `base`.
- phase `status`: `pending | in_progress | done | blocked`
- `satisfies`: GOAL R-IDs this phase delivers (traceability anchor for the review step).
  **Artifact-deliverable R-IDs.** Some requirements are met by a *committed document* — a research
  audit, a protocol doc, an assessment — not by CLI-observable behaviour. Attach such an R-ID to the
  phase that produces and commits the artifact, and give that phase a content `verify:`
  (`test -f …`, a `grep -q` for the sections that must exist) rather than forcing a CLI drive.
  **Say so in the phase body**, because it changes who can grade it: the review step blinds its reviewer
  to all of `spec/`, so an R-ID whose evidence lives there is graded by the *orchestrator*, not the
  blind reviewer. Naming it in `TECH.md` is what lets the review skill route it correctly instead of
  reporting an unverifiable requirement.
- `depends_on`: phase ids that must be `done` first (a phase is actionable only when met).
- `parallel`: `true` only for genuinely independent, non-coupled work (docs, tests, isolated leaf
  modules). Any phase touching the profile's `coupled core` is always `false`.
- `hammerable`: `false` marks a correctness/security phase that scope-hammering must **never** cut.
- `hill`: `uphill` (still figuring it out) → `crest` (unknowns resolved) → `downhill` (just
  executing). A phase stuck `uphill` across builds is a raised hand → escalate to the human.
- `attempts`: durable failed-verify counter (absent = 0), bumped by `set_phase.py --phase P<n>
  --record-attempt` on every red verify gate; `next_phase.py` warns at ≥3 — the circuit breaker
  runs on this file, not on session memory.
- `verify`: the exact command that proves the phase (prefer driving the real CLI, not just tests —
  wrap CLI drives in the profile's `throwaway environment` helper, `<helper> sh -c "…"`, so they hit
  a disposable instance, never the developer's real data). A gate carrying `$( )` or quoting the
  calling shell would mangle is set with `set_phase.py --verify-file PATH`, not `--verify`.
- `review.cycle`: completed review passes, auto-incremented by every `set_phase.py --verdict …`;
  REVIEW.md's "Cycle {n}" mirrors it and the ≤3-cycle bound is graded against it. `--verdict approved`
  also clears `review.blocked_reason` unless one is passed explicitly.

## Conventions (apply to every phase)

- Commit conventions, code style, and load-bearing invariants come from the repo's `AGENTS.md` — it
  is the constitution. Walk the sections of its § Invariants that this change touches; that is the
  curated footgun checklist.
- One phase per build-step invocation by default; one atomic commit containing **both** the code and
  the `TECH.md` state change. The branch commit subject is the build step's (the profile's
  `branch commits`), not restated here; branch commits are squashed away at publish per the
  profile's `landing`. Trailers follow the profile's `branch commits`.
- The last phase carries the standing last-phase items: the deferral ledger, and every item the
  previous cycle's last phase carried for a project-level obligation (none: the previous cycle's
  last-phase items were its own write audit and its ledger). A plan that drops one says why in
  `PLAN.md`.
- A PR body (when the profile's `landing` opens one) ends with an attribution naming the actual
  harness, model, and variant.
- A CLI/feature change obeys the profile's `same-commit rules` (§ Conventions in `AGENTS.md`): the
  help text, docs, or generated files it names change **in the same commit**.

### Cycle-specific

- **The gate.** Each phase's `verify:` is `sh spec/config-variant-collision/verify/gate.sh P<n>`;
  its modes (`static`, `suite`, `drive`, `mutants`, `prepush`) and checks are in the script's
  header and `PLAN.md` § 6. It grades the **index**: stage the phase (code, tests, docs and the
  `TECH.md` state change) before running it, and it fails while anything under `src/`, `tests/`,
  `docs/` or `AGENTS.md` is unstaged. `verify/` and `PLAN.md` are frozen at the plan commit, and the
  gate refuses to run when either differs or when its recorded tree id does not match. A checker a
  remediation needs goes in `spec/config-variant-collision/remediation/`.
- **How to run it.** From `$WT`, sandboxed. Set `UV_CACHE_DIR` and `UV_TOOL_DIR` outside the
  repository and `TMPDIR` to a writable directory outside it; the gate leaves its work directory
  there and prints its path. A sandboxed run names `pypi.org` and `files.pythonhosted.org` for uv.
  Tee the output to a log outside `$WT`. Each phase gate takes about 150 s.
- **A surviving mutant is a missing test.** When `mutants` reports a survivor, add or sharpen a test
  in `tests/test_config.py` (in `TestVariantCollision`, under a new name if none fits) or simplify
  the code until the decision is gone; never weaken a test the gate names. Write no defensive or
  short-circuit statement a test cannot reach (`if not new: return`): it makes an equivalent mutant
  and the gate goes red.
- **What the tests may add.** `tests_kept.py` admits, beside the base, only imports, plain
  assignments to new names, and the class `TestVariantCollision` holding test functions (decorated
  at most with `pytest.mark.parametrize`). No fixture, no member added to a base class, nothing
  that reads the source (`inspect`, `__file__`, hashes) or monkeypatches a cmdkit name.
- **The docs checks find, they do not judge.** `change_set.py` checks that the docstrings, the
  `docs/index.rst` passage and the `AGENTS.md` line changed where they should; whether the words
  state the rule (R8) is the review's to grade.
- **Phase bodies are instructions, not reports.** Results go in the build report and the commit
  body, never in a phase body: the ledger reads phase bodies.

---

## Phase P1 — Layers decide variants, and which agrees
**Satisfies:** R1, R2, R3, R4, R6, R7, R8 · **Depends on:** —
**Goal:** a `Configuration` built from layers holds, for each name at each path, only the variants
of the highest layer that sets any of them; attribute access, item access and `which` agree; plain
`Namespace` is untouched; the rule is documented, and § Invariants 2 states it, in the same commit.

- [x] `src/cmdkit/config.py`, module level after `ConfigurationError`, private helpers per
      `PLAN.md` § 2.1, § 2.2 and § 2.4: the sibling helper; the prune; `_apply_layer(target, new)`
      (prune, then `NSCoreMixin.update(target, new)`); a sentinel lookup; the merged-view test (a
      mapping on the way lacks the next key; a step through a non-mapping is not that case); the
      displacement test (sources bottom to top; above one that holds the whole path, one that holds
      a sibling of a key on the path at that key's place and not the key, at any depth). Each gets
      a one-line docstring and annotations; add any `typing` name they need to the existing import.
- [x] `Configuration.extend`: `_apply_layer(self, self.namespaces[name])` in place of
      `super().update(self.namespaces[name])`; the `_` branch stays `self.local.update(mapping)`.
- [x] `Configuration.which`: add the guard of `PLAN.md` § 2.4 as the first statement after
      `namespaces = ...`, raising `KeyError(f'Not found: {path}')`; leave the walk below it as it is,
      character for character.
- [x] Do not touch `src/cmdkit/namespace.py` or any other file under `src/` (the gate checks).
- [x] `Configuration` class docstring: a sentence or two stating the rule, and an `Example:` block
      showing it (`PLAN.md` § 2.5). `docs/index.rst`: a paragraph stating the rule, inside the
      passage that introduces `_env` and `_eval`, after "Accessing the parameter with
      dot-notation …", naming ``_env``, ``_eval`` and the layers.
- [x] `AGENTS.md` § Invariants 2: the line that records the collision and points at
      `issues/config-variant-collision.md` becomes exactly
      "- `name`, `name_env` and `name_eval` are one key across layers: the highest layer that sets
      any of them decides." in the same place. No other line of `AGENTS.md` changes.
- [x] `tests/test_config.py`, `TestConfiguration.test_attribute_expand_multiple_variants`: keep the
      signature and the `cfg = Configuration(...)` statement; the docstring may change; the body
      after it is exactly these four lines, in this order, outside any `with`:
      `assert cfg.nested.a == 1`, `assert cfg.nested.b == 2`,
      `assert cfg.other.secret == 'baz'`, `assert cfg.nested.test == 'bar'`.
      Change no other base test, fixture, import or module-level statement.
- [x] `tests/test_config.py`, a new class `TestVariantCollision` (after `TestConfiguration`), with
      these tests (the gate looks them up by name; their content follows `GOAL.md` "How it is shown"
      and `PLAN.md` § 2.6):
      - `test_pairs`, parametrized over the six ordered pairs of `token`, `token_env`,
        `token_eval` at `section.token`, one test id per pair: the merged view and its iteration
        order, attribute access (variable set with `monkeypatch.setenv`, `echo` for `_eval`), item
        access for both keys, `which` for both keys and for an untouched sibling key, both layers
        equal to their inputs;
      - `test_top_level`, `test_deep` (three levels), `test_suffix_alone` (`conda` low, `conda_env`
        high: `cfg['conda']` and `which('conda')` raise `KeyError`), `test_mapping_values` (a
        mapping displaced by a scalar variant and the reverse; a mapping-valued name set again
        beside another variant still merges depth-first);
      - `test_deciding_layer_ambiguous` (one variant low, the other two high: "has more than one
        variant", the low one absent), `test_namespace_update_unchanged`;
      - `test_no_expansion`: an `_eval` that would `touch` a file under `tmp_path`, `os.getenv`
        monkeypatched to record its calls; construction, `extend`, `dict()`, `repr()`, item access
        and `which` run nothing and read nothing, and the layers equal their inputs;
      - `test_non_string_keys`, `test_double_suffix` (`token`, then `token_env`, then
        `token_env_eval`: only the last remains, `which` raises for the other two, and `cfg.token`
        raises "'token' not found": `PLAN.md` § 3, third row);
      - `test_extend_and_from_local`: a collision added with `extend` after construction (merged
        view, item access, `which`), and `Configuration.from_local` with two TOML files under
        `tmp_path`, `auth` in the first and `auth_eval` in the second: the merged view, attribute
        access, and `which` for both keys and for an untouched key;
      - `test_which_unchanged` (through a higher scalar, both orders: `TypeError` matching "not
        subscriptable"; a nested mapping names the highest layer; a missing key and a bare name with
        only `token_env` raise `KeyError`), `test_which_restored` (`token`, `token_env`, `token`
        again: `which` names the top layer), `test_which_displaced_through_scalar`
        (`x.y`, then `x = 5`, then `x.y_env`: item access and `which` raise `KeyError`),
        `test_which_through_scalars` (a layer without `x` beside `x.y`, `x = 5`, `x.z`; `x.y` and
        `x.y_env` under a higher `x = 5`; a deciding layer holding `token` and `token_env` beneath
        a scalar and a fresh mapping: each raises `TypeError` matching "not subscriptable").
- [x] Stage everything, run the verify, then commit code, tests, docs, `AGENTS.md` and the
      `TECH.md` state change together.
- [x] Review cycle 1, F1: in the displacement test, a lower source counts as holding a key on the
      path when it holds the path down to that key (a scalar prefix included), not only the whole
      path, so `which` raises `KeyError` where item access does for a path through a scalar that a
      higher variant displaced. A path through a scalar with no displacement on it keeps its
      `TypeError`, and the two in-place shapes of GOAL C8 keep today's answer. Pin it in
      `TestVariantCollision.test_which_displaced_scalar_prefix`: `u = 0` under `u_env` with
      `which('u', 't')` and `which('u', 't', 'v')`; `s.token = 5` under `s.token_env` with
      `which('s', 'token', 'a')`; `u = 5` over `u_env` over an unrelated layer, where item access
      and `which` both raise `TypeError`; and the same with a fresh `u = {}` added above, where
      `which` keeps `TypeError`. Run the P1 gate and then the P2 gate on the final tree, and commit
      as P1.
- **Verify:** `sh spec/config-variant-collision/verify/gate.sh P1`: `static P1`, `suite P1`,
  `drive P1`, `mutants`.
- **Touches:** `src/cmdkit/config.py`, `tests/test_config.py`, `docs/index.rst`, `AGENTS.md`.

## Phase P2 — In-place changes follow the rule
**Satisfies:** R5, R6, R7 · **Depends on:** P1
**Goal:** `update` and top-level attribute assignment record into `_` with the rule applied there
and in the merged view; a name whose variant is in the merged view is a parameter for assignment.

- [x] `Configuration.update`: `_apply_layer(self.local, dict(*args, **kwargs))`, then
      `_apply_layer(self, dict(*args, **kwargs))`, each side building its own argument as the two
      calls do today (`PLAN.md` § 2.2). Add a sentence to its docstring's Note: an in-place change
      follows the layers' rule for `_env` and `_eval` variants, in `_` and in the merged view.
- [x] `Configuration.__setattr__`: the in-place branch runs when `name in self` or any sibling of
      `name` is in `self` (`PLAN.md` § 2.3); the other branch is unchanged.
- [x] `tests/test_config.py`, in `TestVariantCollision`:
      - `test_update`: `update` over a layer's different variant at a nested path; `_` holds only
        the new variant, the merged view only it, attribute and item access agree, `which` names
        `_` for it and raises `KeyError` for the old one; the layer equals its input;
      - `test_successive_updates`: `update(token=...)`, then `update(token_env=...)`: `_` and the
        merged view hold only `token_env`, `which('token_env') == '_'`;
      - `test_attribute_assignment`: `cfg.token = v` over a merged view holding `token_env` from one
        layer, and from a collision of two layers: `_` records it, no instance attribute, `which`
        names `_`; then `cfg.token_env = v` over the merged view's `token`: `_` and the merged view
        hold only `token_env`;
      - `test_attribute_assignment_unchanged`: a name with no variant in the merged view sets an
        instance attribute and leaves `_` empty; a present name goes to `_`.
- [x] Deferral ledger: walk P1's and P2's bodies for deferral phrases and confirm each names an
      `issues/` seed with its `ROADMAP.md` entry (`change_set.py` checks the same at P2). This plan
      defers nothing new: its non-goals were seeded at shaping.
- [x] Stage everything, run the verify, then commit code, tests and the `TECH.md` state change
      together.
- **Verify:** `sh spec/config-variant-collision/verify/gate.sh P2`: `static P2` (with the ledger),
  `suite P2`, `drive P2`, `mutants`.
- **Touches:** `src/cmdkit/config.py`, `tests/test_config.py`.

---

## Amendments

- 2026-11-11, review cycle 1, F1 (the maintainer ruled: fix in P1). P1 is reopened with P2 left
  done. `PLAN.md` § 2.4 says the displacement test looks above "a source that holds all of path";
  the fix widens that to a source holding the path down to the displaced key, which `PLAN.md`
  (frozen at the plan commit) does not restate. P1's gate runs unchanged on the final tree, since
  its checks hold with P2 landed, and P2's gate runs after it on the same tree.

---

## How the build step drives this

1. `next_phase.py` prints the next actionable phase (statuses are authoritative; the
   `current_phase` pointer is reconciled against them).
2. Pre-flight: the cycle worktree is clean, on `branch`, and `base` is reachable.
3. Execute every `[ ]` in the phase (consult `PLAN.md` / `research/` for detail).
4. Run the phase's `verify:` command — never advance on a checkbox alone.
5. Amend this file freely if reality diverges (regenerate frontmatter with `set_phase.py`; note the
   amendment in the commit body). STOP and escalate only on a **`GOAL.md` contradiction**.
6. Mark the phase `done`, advance `current_phase`, `--touch`; one `[{category}]` commit; stop and report.
