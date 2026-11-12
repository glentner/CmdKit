# REVIEW — File loading accepts paths and handles, and its errors name the file

> Adversarial QA by `code-review`, run in an isolated/clean context (a subagent; where the runtime
> has none, `code-review`'s sequential fallback). The correctness pass grades the branch diff against
> [`GOAL.md`](GOAL.md) + the repo's `AGENTS.md` § Invariants **only** — it does not see
> `PLAN.md`/`TECH.md` (avoids grading-its-own-homework / plan-sycophancy). Every finding cites an
> **executed** command, not an assertion.

- **Reviewed commit:** c4340c4ad06694b756af0b01b5e45e833ee9ee40  ·  **Base:** develop (`386a09a`)  ·  **Date:** 2026-11-11
- **Verdict:** changes-requested
- **Cycle:** 1 of ≤3. Mirrors `review.cycle` in `TECH.md`.

A single fresh reviewer graded the change, with no `debate`. Its inputs were `GOAL.md`, the review
rubric, `AGENTS.md`, the runnable worktree, and the diff and log against `origin/develop` with
`spec/` excluded. It ran no sequential fallback. No R-ID is met by a committed `spec/` artifact, so
the reviewer graded all eight. Its probes and logs are in the worktree's ignored `.local/review1/`.

**Contract history.** `GOAL.md` has one commit after the shape commit: `072a36f` adds clarifications
C3–C5, ruled at plan sign-off. It is additive, changes no R-ID's text, and comes before the first
build commit (`d474800`), so the build did not drift the contract. The review graded `GOAL.md` at
HEAD, C3–C5 included.

## Verification run

- **The profile's `verify`** (offline, through uv's build backend): 175 passed on Python 3.9.25 and
  175 passed on Python 3.14.6 (`.local/review1/verify.log`).
- **Base tests against HEAD's source:** the 156 tests collected from `tests/` at `386a09a` all pass
  on 3.9 and 3.14 (`base_tests_vs_head.log`). `tests/` changes by 247 additions and 0 deletions.
- **Differential drive, base against HEAD,** on both Pythons. The probe covers str paths, text
  handles, return types, subclass types, `**options`, YAML, Unicode, missing-file and directory
  errors, unknown `ftype`, `Configuration` layers, and no `_env`/`_eval` expansion on load. The
  transcripts are identical (`probe_diff.diff` is empty).
- **R1 probe:** 58 of 58 checks pass on 3.9 and 3.14, and again on 3.10–3.13 (`probe_r1*.log`).
  - Paths given as str (absolute and relative), `pathlib.Path` and a bare `os.PathLike`.
  - Loaders `from_toml`, `from_tml`, `from_json`, and `from_local` by extension and by `ftype`.
  - `Configuration.from_local`.
  - Each raises the decoder's own type, is a `ValueError`, carries the path and the decoder's
    message, and keeps `lineno`/`colno`. Handle errors are unchanged (C2).
- **R3/R4 probe:** run on base and HEAD, 3.9 and 3.14 (`probe_r3_r4.*.log`).
- **Handle probe** (`probe_handles.log`): text and binary handles, tempfile wrappers and
  `codecs.open`, across both readers and writers. This is F1's evidence.
- **Mutation controls,** on out-of-tree copies (`mutants.log`). Each of these mutants is killed by
  the new tests on both Pythons:
  - no file naming
  - no text-handle branch
  - no bytes decode
  - `hasattr` on the instance
  - JSON accepting str only
  - `cls.__class__.__name__`
  - an empty exclusion list
- **Spec-ID grep** over `src/`, `tests/` and the diff's added lines: none (`spec_id_grep.log`).
- **Windows text-layer emulation** (`winsim.py`, `winsim*.log`). A pytest plugin swaps in `_pyio.open`
  with `os.linesep = '\r\n'` and a cp1252 locale encoding.
  - HEAD: 2 failed and 173 passed on 3.9 and 3.14. The two failures are F2.
  - Control, base tests on base source and on HEAD source: 156 passed each.
- **The docs:** `uv run --locked --group docs sphinx-build -W` on Python 3.12 prints "build
  succeeded". The rendered `api/namespace.html` carries `os.PathLike` 8 times and `api/config.html`
  2 times (`.local/review1/orch/sphinx.log`). That presence check is a plain grep over the rendered
  HTML; `AGENTS.md` documents no check form for the docs.
- **Not observed:**
  - GitHub Actions on this branch. This step has no CI access, and the `windows-latest` legs are
    predicted red by F2.
  - The release gate's full suite on 3.10–3.13. The local cache lacks pyyaml for those; a subset
    without pyyaml passed there (10 each, `release_gate_pythons.log`).

## Requirement → evidence matrix

Every row was verified by the blind reviewer; the docs render in R8 was added afterwards.

| R-ID | Implemented by (file/commit) | Verified how | Status |
|------|------------------------------|--------------|--------|
| R1 | `namespace.py` `_name_the_file`, the decode `try`/`except` in `from_toml` and `from_json` (`c4340c4`) | `probe_r1.py` on 3.9–3.14; `verify` | ✅ |
| R2 | `(str, os.PathLike)` checks in every loader and writer; `Configuration.from_local` annotation (`d474800`) | `probe_handles.py` R2 lines (byte-identical writes, equal loads, by extension and `ftype`); `probe_yaml_path.py`; `verify` | ✅ |
| R3 | the `try`/`except AttributeError` removed from `from_local` and `to_local` (`d474800`) | `probe_r3_r4.py`: `AttributeError`, `KeyError`, `ValueError` and `NotImplementedError` propagate unchanged on HEAD and are masked on base | ✅ |
| R4 | the class-level lookup with its exclusion list, and `cls.__name__` (`d474800`) | `probe_r3_r4.py`: `ini`, `cfg`, empty, `env`, `dict`, `local`, `INI` and `TOML` on `Namespace` and a subclass; C4 and C5 hold | ✅ |
| R5 | `from_toml` decodes a bytes read (`d474800`) | `probe_handles.py`: `open(p, 'rb')`, `BytesIO`, `NamedTemporaryFile('w+b')` and text handles load equal | ✅ |
| R6 | `io.TextIOBase` branch in `to_toml` (`d474800`) | `probe_handles.py`: `open(p, 'w')`, `StringIO` and `BytesIO` agree; other text handles fail (F1) | ❌ partial |
| R7 | (no change) | base `tests/` against HEAD, 156 passed on each Python; `probe_diff.diff` empty | ✅ |
| R8 | docstrings on every method R2 names and on `Configuration.from_local`, in the same commits as the code | read at HEAD; `docs/api/*.rst` are `automethod` only and state no argument type; `sphinx-build -W` render read | ✅ |

Unmapped changes (possible scope creep): none. `issues/namespace-file-loading.md` moves from
`status: unshaped` to `adopted:namespace-file-loading`. That is lifecycle bookkeeping, and its
citations are accurate for the base.

## Findings

Severity: **CRITICAL** (a violation of any numbered section of § Invariants is auto-CRITICAL,
**including lettered subsections**; a § Conventions violation is **HIGH**) · **HIGH** · **MEDIUM** ·
**LOW**. Verdict: **CONFIRMED** (reproduced) vs **PLAUSIBLE** (suspected, needs human triage). Only
CONFIRMED findings auto-loop to `code-build`.

### F1 [MEDIUM/CONFIRMED] `to_toml` still rejects text handles that don't derive from `io.TextIOBase`
- **Where:** `src/cmdkit/namespace.py:267`
- **Failure scenario:** `to_toml` decides whether a handle is text by its class. A text handle of
  any other class falls through to the binary writer, which raises the `TypeError` that R6 removes:
  - `ns.to_toml(tempfile.NamedTemporaryFile('w'))` → `TypeError: write() argument must be str, not bytes`
  - `tempfile.SpooledTemporaryFile(mode='w+')` → the same `TypeError`
  - `codecs.open(p, 'w')` → `TypeError: utf_8_encode() argument 1 must be str, not bytes`
  Meanwhile `to_json` accepts the same `NamedTemporaryFile('w')`, and `from_toml` reads it in both
  modes. The new `to_toml` docstring says "a handle may be text or binary".
- **Evidence:** `probe_handles.py` → `.local/review1/probe_handles.log`, same result on 3.9 and
  3.14. Base fails the same way: this is an incomplete fix, not a regression.
- **Touches requirement:** R6 ("SHALL write to a text handle").
- **Route (the property):** `to_toml` writes text to every handle that takes `str` and bytes to every
  handle that takes `bytes`, whatever the handle's class. That covers built-in files, `io.StringIO`
  and `io.BytesIO`, the `tempfile` wrappers and `codecs` writers, and never raises `TypeError` for a
  handle of either kind. Pin the other side too: every binary handle that works today (`open(p, 'wb')`,
  `BytesIO`, `NamedTemporaryFile('w+b')`, a binary `SpooledTemporaryFile`) receives the same bytes as
  before. `from_toml` decides the same question by what the handle returns, and `to_toml` decides it
  by class. The fix should leave one rule that both directions follow.

### F2 [MEDIUM/CONFIRMED] Two new tests assume POSIX text I/O and will fail on the `windows-latest` CI legs
- **Where:** `tests/test_config.py:1251` (`test_toml_text_handle`) and `tests/test_config.py:1320`
  (`test_other_errors_unchanged`)
- **Failure scenario:** the `tests` workflow, which must be green before landing, runs
  `windows-latest` on 3.9 and 3.14.
  - `test_toml_text_handle` compares the LF bytes of `StringIO`/`BytesIO` with bytes written through
    text-mode files (`to_toml(path)`, `open(handle, 'w')`). Windows translates those to CRLF.
  - `test_other_errors_unchanged` expects `open(json_path)`, with no encoding, to raise
    `UnicodeDecodeError` on byte `0xff`. Windows' default cp1252 decodes it, so the test fails with
    "DID NOT RAISE".
  The library's behaviour is not at fault.
- **Evidence:** reproduced under the Windows text-layer emulation, not on a Windows host. HEAD gives
  2 failed and 173 passed on 3.9 and 3.14; base tests give 156 passed against both base and HEAD
  source (`winsim.log`, `winsim_detail.log`). TOML decoding normalises CRLF, so the decode-error
  tests are unaffected (`winsim_check.log`). The PR's own CI is the platform check.
- **Touches requirement:** the profile's `ci` gate, and the evidence for "How it is shown" 5 and 6
  (R6, R7).
- **Route (the property):** every test this diff adds holds on every OS and Python in the CI matrix.
  None may assume LF newlines from a text-mode write or a UTF-8 default encoding. Pin the other side:
  on POSIX the tests still assert byte-equal TOML across `StringIO`, `BytesIO`, a handle and a path,
  and `UnicodeDecodeError` for undecodable input.

### Observations (not findings)

- `to_local` now looks up its writer on the class, so a key such as `to_ini_eval` no longer runs its
  command when the format is checked (`probe_r3_r4.base.3.14.log`: "marker ran? True" on base). This
  is in keeping with § Invariants 2, and part of R4's dispatch rewrite.
- The `from_toml` and `to_toml` docstrings now say which handle modes they take, and the loaders'
  docstrings say that a decode error names the file. § Conventions requires this for the public
  behaviour R1, R5 and R6 change, so it is in scope. `to_toml`'s "text or binary" claim holds only
  once F1 is fixed.
- The `to_json` signature (`src/cmdkit/namespace.py:272`) is 125 characters. Every other line in
  `src/` at the base is 120 or fewer. No rule states a line length, so this is style and not graded.

## Human-gate triggers

- **Triggered.** F1 is CONFIRMED in `src/cmdkit/namespace.py`, a path on § Invariants'
  high-blast-radius list. It needs the maintainer's explicit sign-off before the cycle goes further,
  and the gate holds until publish.
- F2 is in `tests/test_config.py`, which is not on the list. Neither finding violates a section
  tagged *[human gate]*.

## Optional completeness sub-pass (separate reviewer; may see TECH.md)

- Not run: not requested for this cycle.
