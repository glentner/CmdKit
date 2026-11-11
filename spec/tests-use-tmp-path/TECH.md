---
slug: tests-use-tmp-path
title: Tests write only to pytest's temporary directories
kind: fix
appetite: small
status: in_review
branch: fix/tests-use-tmp-path
base: develop
current_phase: done
last_updated: '2026-11-10'
phases:
- id: P1
  name: Move the configuration tests' files to tmp_path, with the verify row
  status: done
  satisfies:
  - R1
  - R2
  - R3
  - R4
  - R5
  - R6
  depends_on: []
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/tests-use-tmp-path/verify/gate.sh P1
review:
  last_reviewed_commit: ''
  verdict: none
  blocked_reason: ''
  cycle: 0
---

# TECH.md — Tests write only to pytest's temporary directories

The **context engine and finite-state machine** for building this fix. The YAML frontmatter above
is the resume ground-truth (read it from the cycle worktree with the factory's `next_phase.py`);
the per-phase checklist below is the work. The build step executes the next actionable phase, runs
its `verify:` command, updates state with the factory's `set_phase.py`, and makes one atomic
code+state commit.

- **Vision / requirements (locked):** [`GOAL.md`](GOAL.md) — R-IDs are the contract.
- **Authoritative design:** [`PLAN.md`](PLAN.md).
- **Backing research:** none (a lean plan; the design's open questions are settled in
  [`PLAN.md`](PLAN.md) § 4).

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
  last-phase items were its own CI evidence and its ledger). A plan that drops one says why in
  `PLAN.md`.
- A PR body (when the profile's `landing` opens one) ends with an attribution naming the actual
  harness, model, and variant.
- A CLI/feature change obeys the profile's `same-commit rules` (§ Conventions in `AGENTS.md`): the
  help text, docs, or generated files it names change **in the same commit**.

### Cycle-specific

- **The gate.** P1's `verify:` is `sh spec/tests-use-tmp-path/verify/gate.sh P1`; its modes and
  checks are in the script's header and `PLAN.md` § 6. It reads committed state (an export of HEAD,
  and the commits since the merge-base with `origin/develop`), so it grades the phase only after the
  phase's commit, or in a throwaway worktree with the work committed there. `verify/` is frozen at
  the plan commit, and the gate refuses to run when it differs; a remediation checker goes in
  `spec/tests-use-tmp-path/remediation/`.
- **How to run it.** From `$WT`. Set `UV_CACHE_DIR` and `UV_TOOL_DIR` to per-step directories
  outside the repository, and `TMPDIR` to a writable directory outside it too: the gate makes its
  work directory there and leaves it for inspection. Two modes need opposite hosts, and each
  probes for its own: `R2` (and so `P1`) needs `/tmp` writable, so run `P1` with the sandbox off;
  `tmpdenied` needs `/tmp` denied, so run it with the sandbox on (it runs the profile's `verify`
  and then `concurrent` there, as GOAL's "How it is shown" 3 has them). The other modes run either
  way. A sandboxed run names `pypi.org` and `files.pythonhosted.org` for uv. Tee the output to a
  log outside `$WT`.
- **The review re-runs** `gate.sh audit` (the one-off write audit, C2) and `gate.sh tmpdenied` on
  the review host.
- **Phase bodies are instructions, not reports.** Results go in the build report and the commit
  body, never in a phase body: the ledger reads phase bodies.

---

## Phase P1 — Move the configuration tests' files to tmp_path, with the verify row
**Satisfies:** R1, R2, R3, R4, R5, R6 · **Depends on:** —
**Goal:** the four tests of `tests/test_config.py` that write files write them in the directory
pytest gives each of them; the module creates nothing when imported; the profile's `verify` row
loses its `/tmp` note in the same commit; every test asserts what it asserted at `b9efaca`.

- [x] Host precondition for R2: `/tmp/cmdkit` must not exist on the build host. An older run of
      the suite leaves it behind; if it is there, stop and ask the operator to move it aside. The
      builder never removes it itself.
- [x] `tests/test_config.py`: delete the comment `# ensure temporary directory exists`, the
      `TMPDIR = '/tmp/cmdkit/config'` line, the `os.makedirs(TMPDIR, exist_ok=True)` line and the
      blank line above them. Add `from pathlib import Path` to the `# standard libs` group, between
      `from io import StringIO` and `from string import ascii_letters`.
- [x] Give `TestNamespace.test_factories`, `TestNamespace.test_from_local`,
      `TestNamespace.test_to_local` and `TestConfiguration.test_from_local` a last parameter
      `tmp_path: Path`, and write `{tmp_path}` for `{TMPDIR}` in each of their f-strings. Change
      nothing else in them: the call sequence stays, including the loop at the top of
      `TestNamespace.test_from_local` that removes files a fresh directory doesn't have.
- [x] `AGENTS.md` § Factory, the Profile table's `verify` row: delete its last sentence, from
      `Until` through `allow that path`, and keep the rest of the row as it is (the backticked
      command unchanged, one space before the closing `|`). No other line of `AGENTS.md` changes.
- [x] Commit `tests/test_config.py`, `AGENTS.md` and the `TECH.md` state change together: R6 asks
      for one commit, and the gate finds the first commit in which each loses `/tmp`.
- [x] After the commit, `sh spec/tests-use-tmp-path/verify/gate.sh P1` with the sandbox off (the
      verify below).
- [x] R3 in its native form, and R4 under it: `sh spec/tests-use-tmp-path/verify/gate.sh tmpdenied`
      with the sandbox on; put its last lines in the build report.
- [x] Deferral ledger: walk this phase body for deferral phrases and confirm each names an
      `issues/` seed with its `ROADMAP.md` entry (`change_set.py` checks the same mechanically).
- **Verify:** `sh spec/tests-use-tmp-path/verify/gate.sh P1`: `static` (`change_set.py`,
  `same_behaviour.py ast`), `selftest` (the hook against its canary suite on 3.9 and 3.14),
  `audit` (R1 and R5 on 3.9 and 3.14), `concurrent` (R4 and portable R3), then `R2` (which needs
  the sandbox off and `/tmp/cmdkit` absent).
- **Touches:** `tests/test_config.py`, `AGENTS.md`.

---

## How the build step drives this

1. `next_phase.py` prints the next actionable phase (statuses are authoritative; the
   `current_phase` pointer is reconciled against them).
2. Pre-flight: the cycle worktree is clean, on `branch`, and `base` is reachable.
3. Execute every `[ ]` in the phase (consult `PLAN.md` for detail).
4. Run the phase's `verify:` command — never advance on a checkbox alone.
5. Amend this file freely if reality diverges (regenerate frontmatter with `set_phase.py`; note the
   amendment in the commit body). STOP and escalate only on a **`GOAL.md` contradiction**.
6. Mark the phase `done`, advance `current_phase`, `--touch`; one `[{category}]` commit; stop and report.
