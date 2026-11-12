---
slug: namespace-file-loading
title: File loading accepts paths and handles, and its errors name the file
kind: fix
appetite: small
status: blocked
branch: fix/namespace-file-loading
base: develop
current_phase: done
last_updated: '2026-11-11'
phases:
- id: P1
  name: Paths, handles and dispatch
  status: done
  satisfies:
  - R2
  - R3
  - R4
  - R5
  - R6
  - R7
  - R8
  depends_on: []
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/namespace-file-loading/verify/gate.sh P1
- id: P2
  name: Decode errors name the file
  status: done
  satisfies:
  - R1
  - R7
  - R8
  depends_on:
  - P1
  parallel: false
  hammerable: false
  hill: uphill
  verify: sh spec/namespace-file-loading/verify/gate.sh P2
review:
  last_reviewed_commit: c4340c4ad06694b756af0b01b5e45e833ee9ee40
  verdict: changes-requested
  blocked_reason: 'Review cycle 1: F1 to_toml rejects non-TextIOBase text handles (R6); F2 two new tests fail on Windows CI. Human gate: F1 in namespace.py'
  cycle: 1
---

# TECH.md — File loading accepts paths and handles, and its errors name the file

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
  last-phase items were its own tests and its ledger). A plan that drops one says why in `PLAN.md`.
- A PR body (when the profile's `landing` opens one) ends with an attribution naming the actual
  harness, model, and variant.
- A CLI/feature change obeys the profile's `same-commit rules` (§ Conventions in `AGENTS.md`): the
  help text, docs, or generated files it names change **in the same commit**.

### Cycle-specific

- **The gate.** Each phase's `verify:` is `sh spec/namespace-file-loading/verify/gate.sh P<n>`; its
  modes (`static`, `suite`, `drive`, `mutants`, `prepush`) and checks are in the script's header and
  `PLAN.md` § 6. It grades the **index**: stage the phase (code, tests, docstrings and the `TECH.md`
  state change) before running it, and it fails while anything under `src/`, `tests/`, `docs/` or
  `AGENTS.md` is unstaged. `verify/` and `PLAN.md` are frozen at the plan commit, and the gate
  refuses to run when either differs or when its recorded tree id does not match. A checker a
  remediation needs goes in `spec/namespace-file-loading/remediation/`.
- **How to run it.** From `$WT`, sandboxed. Set `UV_CACHE_DIR` outside the repository and `TMPDIR`
  to a writable directory outside it; the gate leaves its work directory there and prints its path.
  A sandboxed run names `pypi.org` and `files.pythonhosted.org` for uv. Tee the output to a log
  outside `$WT`. P1's gate takes about 60 s, P2's about 75 s.
- **A known flake.** `tests/test_app.py::test_app_invalid_options` fails about 1 in 40 runs per
  Python, and the gate runs the suite four times (`issues/test-invalid-options-help-prefix.md`).
  This cycle touches nothing under it; a red of that test alone takes the build step's known-flake
  route.
- **Write only what `PLAN.md` § 2 names.** Every other line of `src/cmdkit/namespace.py` and
  `src/cmdkit/config.py` stays character for character: the mutant sweep grades every added line,
  and a rewritten line it did not plan for becomes a decision the tests must pin.
- **A surviving mutant is a missing test.** When `mutants` reports a survivor, add or sharpen a test
  in `TestFileLoading` (under a new name if none fits) or simplify the code until the decision is
  gone; never weaken a test the gate names. Write no defensive statement a test cannot reach: it
  makes an equivalent mutant and the gate goes red.
- **What the tests may add.** `tests_kept.py` admits, beside the base, only imports (and a
  `sys.version_info` block holding only imports, for the TOML decoder), plain assignments to new
  names, and the class `TestFileLoading` holding test functions (decorated at most with
  `pytest.mark.parametrize`). No fixture, no module-level helper class (define a `Namespace` subclass
  or a bare `os.PathLike` class inside the test that needs it), no member added to a base class,
  nothing that reads the source (`inspect`, `__file__`, hashes) or monkeypatches a cmdkit name.
  Every test writes under `tmp_path`.
- **The docs checks find, they do not judge.** `change_set.py` checks that the docstrings name
  `os.PathLike` (and at P2 the decode error) and change in the same commit as the code; whether the
  words say what GOAL asks (R8) is the review's to grade.
- **Phase bodies are instructions, not reports.** Results go in the build report and the commit
  body, never in a phase body: the ledger reads phase bodies.

---

## Phase P1 — Paths, handles and dispatch
**Satisfies:** R2, R3, R4, R5, R6, R7, R8 · **Depends on:** —
**Goal:** every loader and writer takes an `os.PathLike` as it takes a `str`; `from_local` and
`to_local` decide support before calling, so a loader's or writer's own exception comes through as
itself and an unsupported extension names the class and the extension; `from_toml` reads binary
handles and `to_toml` writes text handles; the docstrings say so in the same commit.

- [x] `src/cmdkit/namespace.py`, per `PLAN.md` § 2.1 to § 2.3: `import io` under `# standard libs`;
      `_NOT_FILE_FORMATS` after `T = TypeVar('T')` with its comment; the six `isinstance` tests; the
      dispatch in `from_local` and `to_local` (the `ignore_if_missing` return stays first; support on
      `cls` and on `type(self)`; the call outside any `try`; the two messages); the `from_toml`
      handle branch; the `to_toml` `io.TextIOBase` branch; the annotations.
- [x] Docstrings, `PLAN.md` § 2.5: `from_local`, `to_local`, `from_toml`, `from_yaml`, `from_json`,
      `to_toml`, `to_yaml`, `to_json` each gain a sentence saying a path may be a `str` or an
      `os.PathLike`.
- [x] `src/cmdkit/config.py`, `PLAN.md` § 2.6: `import os`; the `**files` annotation; the docstring
      sentence. Nothing else in the file.
- [x] `tests/test_config.py`: the imports the tests need, and a new class `TestFileLoading` at the
      end of the module with these tests (the gate looks them up by name; their content follows
      `GOAL.md` "How it is shown" 2 to 5 and `PLAN.md` § 2.7):
      - `test_path_round_trip`: for `toml`, `tml`, `yaml`, `yml`, `json`, with a `pathlib.Path` and
        with a bare `os.PathLike` object: `to_local` by extension and by `ftype`, the direct writer,
        `from_local` by extension and by `ftype`, the direct loader; the bytes written equal those
        written by a `str` path, and every load equals the namespace written;
      - `test_path_ignore_if_missing`: a missing `Path` with `ignore_if_missing=True`, by extension
        (`ini` included) and by `ftype`, returns an empty `Namespace`; without it,
        `FileNotFoundError`;
      - `test_configuration_path_layers`: `Configuration.from_local` with `Path` layers (one
        missing): the merged view, `which`, the missing layer empty;
      - `test_loader_error_propagates`, `test_writer_error_propagates`: subclasses whose `from_json`
        / `to_json` raise `AttributeError('inner')` and `KeyError('k')`, by `str` and by `Path`: the
        very exception object comes out of `from_local` / `to_local`;
      - `test_unsupported_extension`: `ini`, `dict`, `env`, `local`, the file present, on `Namespace`
        and on a subclass, through `from_local` and `to_local`: the exact messages of `PLAN.md`
        § 2.2; a namespace holding only a `to_<ext>` key, and another holding only a
        `to_<ext>_eval` key (a `touch` under `tmp_path`), each raise the same, run nothing and write
        no file;
      - `test_toml_binary_handle`: `open(p, 'rb')`, `open(p)` and `io.BytesIO` load the same namespace;
      - `test_toml_text_handle`: `io.StringIO`, `io.BytesIO`, `open(p, 'w')` and a path write the same
        bytes, and the text reads back.
- [x] Stage everything, run the verify, then commit code, tests, docstrings and the `TECH.md` state
      change together.
- **Verify:** `sh spec/namespace-file-loading/verify/gate.sh P1`: `static P1`, `suite P1`,
  `drive P1`, `mutants`.
- **Touches:** `src/cmdkit/namespace.py`, `src/cmdkit/config.py`, `tests/test_config.py`.

## Phase P2 — Decode errors name the file
**Satisfies:** R1, R7, R8 · **Depends on:** P1
**Goal:** a TOML or JSON file given by path that fails to decode, through any entry point, raises
the decoder's own error with the path at the head of its message and its `lineno` and `colno`
kept; handle errors and every other error are unchanged; the two docstrings say so.

- [x] `src/cmdkit/namespace.py`, `PLAN.md` § 2.4: the helper `_name_the_file` after
      `_as_namespace`, with a one-line docstring and annotations, setting a one-tuple `args`; the
      path branches of `from_toml` and `from_json` catch exactly the decoder's error class, call the
      helper and re-raise with a bare `raise`; the `return cls(data)` after the `with`. The handle
      branches stay as P1 left them.
- [x] Docstrings, `PLAN.md` § 2.5: `from_toml` names `TOMLDecodeError` and `from_json` names
      `JSONDecodeError`, each saying a file given by path that fails to decode raises it with the
      file named in its message.
- [x] `tests/test_config.py`, in `TestFileLoading`:
      - `test_decode_error_names_file`, parametrized over `toml` and `json` and over `str` and
        `Path`: `[a]\nx = \n` and `{"a": }` through the direct loader, `from_local` by extension and
        by `ftype`; the error is the decoder's type (import `TOMLDecodeError` from `tomllib` or
        `tomli` by version) and a `ValueError`; its `args` is exactly
        `(f'{path}: {reference}',)` where `reference` is the decoder's own error on the same text;
        `lineno` and `colno` equal the reference's where it has them;
      - `test_decode_error_configuration`: `Configuration.from_local` with a good layer and a bad
        one, for both formats: the error names the bad file;
      - `test_decode_error_handle_unchanged`: TOML from `io.StringIO` and `io.BytesIO`, JSON from
        `io.StringIO`: the decoder's own message, unchanged;
      - `test_other_errors_unchanged`: invalid UTF-8 in a TOML and a JSON file loaded by path raises
        a `UnicodeDecodeError` whose `args` and `str()` equal those of decoding the same bytes
        directly (`bytes.decode()` for TOML, a text-mode `read()` for JSON); a missing file raises
        `FileNotFoundError`.
- [x] Deferral ledger: walk P1's and P2's bodies for deferral phrases and confirm each names an
      `issues/` seed with its `ROADMAP.md` entry (`change_set.py` checks the same at P2). This plan
      defers nothing: GOAL's non-goals need no seed, and `environ-without-prefix` is seeded already.
- [x] Stage everything, run the verify, then commit code, tests, docstrings and the `TECH.md` state
      change together.
- **Verify:** `sh spec/namespace-file-loading/verify/gate.sh P2`: `static P2` (with the ledger),
  `suite P2`, `drive P2`, `mutants`.
- **Touches:** `src/cmdkit/namespace.py`, `tests/test_config.py`.

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
