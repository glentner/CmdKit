# PLAN — Tests write only to pytest's temporary directories

> **Status:** Draft for review · **Last updated:** 2026-11-10
> **Authoritative technical design.** The *how*. Vision/contract is [`GOAL.md`](GOAL.md);
> the phased executable roadmap is [`TECH.md`](TECH.md). There is no `research/`: the appetite is
> small and no research trigger for a fan-out fired (§ 4). Every design element traces to a GOAL R-ID.

## 1. Summary

The four tests in `tests/test_config.py` that write files take pytest's `tmp_path` fixture and
write where it points, in place of the module-level `TMPDIR = '/tmp/cmdkit/config'` that importing
the module creates today. The change is mechanical: one import, four signatures, `{TMPDIR}` read as
`{tmp_path}` in their f-strings, and the module's two `/tmp` lines gone. The profile's `verify` row
in `AGENTS.md` drops its `/tmp` sentence in the same commit. One phase carries it all. The work of
the plan is the gate: a write audit through a Python audit hook, run on both of the profile's
Pythons, alone and two at once, plus a syntax-tree comparison that pins every test's behaviour to
the base's.

## 2. Design

### 2.1 The test change (`tests/test_config.py`)

- Delete the module-level comment `# ensure temporary directory exists`, `TMPDIR = '/tmp/cmdkit/config'`
  and `os.makedirs(TMPDIR, exist_ok=True)`, with the blank line above them. Importing the module
  then creates nothing (R1, R3: today it fails at collection where `/tmp` is denied and the
  directory is absent).
- Add `from pathlib import Path` to the `# standard libs` group (for the annotation; the code style
  annotates every test signature already, `-> None`).
- `TestNamespace.test_factories`, `TestNamespace.test_from_local`, `TestNamespace.test_to_local` and
  `TestConfiguration.test_from_local` each take a last parameter `tmp_path: Path`, and each
  `f'{TMPDIR}/…'` becomes `f'{tmp_path}/…'`. The values handed to cmdkit stay strings built the same
  way, with the same file names and extensions, so `Namespace.from_local`'s extension dispatch,
  `ignore_if_missing`, `to_local`'s `NotImplementedError` for `.special`, and
  `Configuration.from_local`'s three layers see what they saw (R5).
- Each test gets its own directory, so no test sees another's files, and two runs never share one
  (R4). The clearing loop at the top of `TestNamespace.test_from_local` stays: it is part of the
  call sequence R5 keeps, and on a fresh directory it removes nothing, which is what the test then
  asserts (every `from_local` raises `FileNotFoundError`). Today it depends on test order; after,
  it doesn't.
- `os` stays imported: the tests still use `os.path.exists`, `os.remove` and `os.environ`.
- Nothing else under `tests/` changes. `tests/test_app.py`'s `NONEXISTENT-FILE` only reads (a
  non-goal).

### 2.2 The profile's `verify` row (`AGENTS.md`)

Delete the row's last sentence, "Until `issues/tests-use-tmp-path.md` lands, the suite writes to
`/tmp/cmdkit/config`, so a sandboxed run must allow that path", and keep the rest of the row,
command included, byte for byte (R6). The sentence also names this cycle's seed, which the roadmap
step retires after landing, so the row would point at a stale seed if it stayed. Same commit as
§ 2.1.

### 2.3 The gate (`spec/tests-use-tmp-path/verify/`)

`gate.sh` (POSIX `sh`) dispatches modes; three Python checkers carry the logic, and two data files
are frozen at the plan commit. Suite runs use the profile's environment (`uv run --isolated
--no-project --python {3.9,3.14} --with pytest --with hypothesis --with tomli --with tomli-w --with
pyyaml --with-editable <export>`) on an export of HEAD (`git archive`), never the working copy.

- **`write_audit.py run`** installs a `sys.addaudithook` hook, then imports pytest and runs
  `pytest.main`. It records:
  - every `open` with write flags (`O_WRONLY`, `O_RDWR`, `O_APPEND`, `O_CREAT`, `O_TRUNC`,
    `O_EXCL`; the mode string when there are no flags), from `io.open` and `os.open` alike;
  - `os.mkdir`, `os.rename` (and `os.replace`), `os.remove`, `os.rmdir`, `os.symlink`, `os.link`
    (its source counts as modified: a hard link in `tmp_path` writes the outside file),
    `os.truncate`, `os.utime`, `os.chmod`, `os.chown`, `os.chflags`, `os.setxattr`,
    `os.removexattr`, `shutil.rmtree`, `sqlite3.connect`, and an AF_UNIX `socket.bind`;
  - every `open` for reading made while a test runs (for R4);
  - every spawn (`subprocess.Popen`, `os.system`, `os.posix_spawn`, `os.exec`, `os.spawn`,
    `os.startfile`, `pty.spawn`), every fork, and every `ctypes` library load;
  - the files under the root before and after the run, and the threads still alive when
    `pytest.main` returns.

  Each path is resolved at the event: relative to the working directory, or to its `dir_fd`
  (`/proc/self/fd` on Linux, `fcntl.F_GETPATH` on macOS; `shutil.rmtree` removes through
  `dir_fd`), and a file-descriptor argument to its path. Every directory component is resolved, so
  `/tmp` and `/private/tmp` compare equal, and so is the last one for the events that follow it
  (`open`, `truncate`, `utime`, `chmod`, ...), so a write through a symlink in `tmp_path` is
  recorded where it lands. An unresolvable path is a violation. Each record carries its *writer*,
  the innermost frame outside the standard library (`test`, `cmdkit`, `pytest`, `hypothesis`,
  `import` for the frozen import system, `stdlib` when there is none), and whether a test frame is
  on the stack. Recording runs until interpreter shutdown: the log is written by the first
  `atexit` handler registered, so `atexit` callbacks and non-daemon threads a test leaves behind
  are recorded too.
- **`write_audit.py check`** (R1): every write lies under the allowed directory (the run's
  `--basetemp`, or its system temporary directory where pytest's default basetemp lives), or is a
  C1 cache write: under `.pytest_cache/` (or the `pytest-cache-files-*` directory pytest builds it
  in), `.hypothesis/`, or a `__pycache__/` under the root or an import root, *and* asked for by the
  import system, pytest or Hypothesis, never by a test or by cmdkit (a write pytest's `cache`
  fixture makes for a test is the test's). pytest's own output capture is set aside too (row 1
  below). Every spawn is a shell running a plain `echo` (the suite's `_eval` values); a fork, or a
  `ctypes` load by a test or cmdkit, is a violation. No thread outlived `pytest.main`. Nothing
  under the root changed outside the caches. pytest exited 0. The base names of the files the
  tests (or cmdkit, called from a test) opened for writing are exactly `written-names.txt`: the 13
  names the base writes. That proves the hook saw the tests' own writes and pins R5's file names.
- **`write_audit.py cross`** (R4): no file a test of one run wrote (outside the caches) was read or
  written by a test of the other, and each run's tests wrote something. A test's write is one its
  own code, cmdkit or the standard library asked for (a thread running standard-library code
  counts), or any other write made while a test frame is on the stack, except the import system's,
  Hypothesis's, and pytest's bookkeeping for its numbered directories (row 4 below).
- **`write_audit.py selftest`**: a canary suite in a fresh directory writes outside its basetemp by
  every route above (open `w`, `a` and `r+`, `os.open`, `pathlib`, `makedirs`, rename, replace,
  remove, rmdir, `shutil.rmtree` through `dir_fd`, `mkdir` and `rename` through `dir_fd`, truncate,
  utime, chmod, `fchmod` on a descriptor, chflags where it exists, symlink, a write through a
  symlink in `tmp_path`, a hard link from `tmp_path`, SQLite, a relative path, a test's own write
  into `.hypothesis/`, the `cache` fixture, a test's `tempfile.mkstemp` in the system temporary
  directory, a `touch` spawn, a fork, a `ctypes` load, an `atexit` callback, a thread that writes
  after `pytest.main` returns), and each must be reported; its `tmp_path` writes and an `echo`
  spawn must not be. Two canary runs share one fixed file directly and one through a thread
  running `shutil.copyfile`, and `cross` must report both and no pytest bookkeeping. A broken hook
  goes red here, before its verdict on the suite counts.
- **`same_behaviour.py ast`** (R5): every other file under `tests/` is the base's, byte for byte, and
  `tests/test_config.py` parses to the base's syntax tree once the move is taken out of both (the
  two module lines from the base; from the branch, the `Path` import and each added last `tmp_path`
  parameter, with `tmp_path` read as `TMPDIR` in that function). Every call, argument, file name
  and assertion is then the base's.
- **`same_behaviour.py passed`** (R5): the short test summary of each whole-suite run reports
  `PASSED` for every one of the 75 node IDs of `base-nodeids.txt`, and nothing failed, errored,
  skipped, xfailed or xpassed. (No test is added: `ast` holds every file under `tests/` to the
  merge-base's, so a rebase onto a `develop` with more tests stays green.)
- **`change_set.py`** (R6, the non-goals, How it is shown 4): since the plan commit (found by its
  subject line alone), only `tests/test_config.py`, `AGENTS.md` and `spec/tests-use-tmp-path/`
  change (an `issues/` seed and `ROADMAP.md` only for a recorded deferral), and nothing under
  `spec/` is a file pytest's rootdir walk would load (`conftest.py`, `test_*.py`, `__init__.py`,
  `pytest.ini` and the like: the repo sets no `testpaths`); `git grep -nE "['\"]/tmp" HEAD --
  tests/` is empty; the only `AGENTS.md` line that changes is the `verify` row, and it changes by
  exactly the deletion of its `/tmp` sentence; the first commit whose `tests/test_config.py` loses
  its quoted `/tmp` literal is the first whose single `verify` row names none of `/tmp`, a sandbox
  or this seed; and the `TECH.md` deferral ledger.

Modes: `static`, `selftest`, `audit` (R1 and R5: `--basetemp` at a fresh directory, `TMPDIR` at
another, both Pythons in turn), `concurrent` (R4 and R3's portable form: both Pythons at once from
one export, a barrier so their runs overlap, `TMPDIR` shared and fresh, pytest's default basetemp;
afterwards each run's own PID must be gone, by `kill -0`, since `pgrep` and `ps` are refused inside
this host's sandbox), `R2` (probes that `/tmp` takes a `mkdir`, since with `/tmp` denied the
absence afterwards proves nothing; then `/tmp/cmdkit` absent before and after a `--basetemp` run on
each Python), `tmpdenied` (R3's native form: probes that `/tmp` refuses a `mkdir`, runs the
profile's `verify` exactly as `AGENTS.md` states it at HEAD with `TMPDIR` at a fresh writable
directory, then `concurrent` under the same denial), and `P1`, the phase's `verify:`: `static`,
`selftest`, `audit`, `concurrent`, `R2`. `P1` therefore runs with the sandbox off, and
`tmpdenied` with it on. Every mode first checks that `verify/` is the plan commit's copy: no
uncommitted change, and no commit since the plan commit touches it. Suite runs unset
`PYTEST_ADDOPTS`, `PYTEST_PLUGINS` and `PYTEST_DEBUG_TEMPROOT`.

### Requirement → design map

| R-ID | Design element(s) that satisfy it |
|------|-----------------------------------|
| R1   | § 2.1, the module lines gone and `tmp_path` in four tests. Shown by `gate.sh audit` (`write_audit.py run`/`check` with `--basetemp` fresh, both Pythons), `selftest` first. |
| R2   | § 2.1. Shown by `gate.sh R2` on a host where `/tmp/cmdkit` is absent. |
| R3   | § 2.1: nothing at import, nothing under `/tmp` but pytest's own temporary directory. Shown natively by `gate.sh tmpdenied` (the profile's `verify` with `/tmp` denied), portably by `gate.sh concurrent` (`TMPDIR` elsewhere, default basetemp, every write under it or in the caches). |
| R4   | § 2.1: a directory per test, per run. Shown by `gate.sh concurrent` (`cross`, both runs passing), run inside `P1` and again under `tmpdenied`. |
| R5   | § 2.1, the change limited to paths. Shown by `same_behaviour.py ast` and `passed`, and `written-names.txt` in `check`. |
| R6   | § 2.2. Shown by `change_set.py` (the row, one commit). |

## 3. Invariant gate (AGENTS.md constitution check)

Checked against `AGENTS.md` § Invariants before the design and again after it was drafted.

- **High-blast-radius paths:** none touched. The change lives in `tests/test_config.py` and one row
  of `AGENTS.md` § Factory; `change_set.py` refuses anything under `src/` and every build file.
- **§ 1 Compatibility:** no behaviour of cmdkit changes; nothing under `src/` changes. The tests
  that pin today's behaviour keep every assertion (`same_behaviour.py ast`).
- **§ 2 Configuration core:** untouched; the tests that exercise loading, `from_local` and
  `to_local` keep their calls and assertions, only their paths move.
- **§ 3 Command line:** untouched.
- **§ 4 Footprint:** the floor stays 3.9: `tmp_path` and `pathlib.Path` exist there, and the gate
  runs the suite on 3.9 and 3.14. No runtime dependency.
- **§ Conventions:** the profile's `verify` row changes only in prose; its command, the CI matrix
  and the release gate keep step, so the "change together" rule has nothing to move. "Point to a
  rule; don't restate it": the deleted sentence was a restatement of this cycle's seed; nothing
  replaces it. No R/P ids enter `tests/`. Code style: the new import goes in its commented group,
  and the new parameters are annotated.

### Deviation justifications

Each row is a reading of how R1–R4 are *shown*, not a bend of an R-ID: R1's SHALL covers the files
a test creates, writes, renames or removes, and every row below sets aside only writes that no test
asks for.

| Deviation | Why needed | Simpler alternative rejected because |
|-----------|-----------|--------------------------------------|
| The audit sets aside pytest's own output capture: `os.devnull`, and anonymous files pytest's code creates directly in the system temporary directory and removes in the same run (plus that directory, opened to make one). How it is shown, 2, says every recorded path lies under `--basetemp` or a tool cache. | `capsys`, and pytest's default capture, open and unlink such files on every run; they are pytest's, not a test's, and C1 names only the three caches. Only writes whose innermost non-standard-library frame is pytest's qualify; a test's own `tempfile.mkstemp` there is a violation (the canary checks it). | Running the audit with `-s` (capture off) changes the run the audit is meant to observe; allowing all of `TMPDIR` would pass a test's own temporary files outside `tmp_path`. |
| C1's `__pycache__/` is read to include the bytecode the import system and pytest's assertion rewriting write into the tool environment (uv's environment, an import root), not only "in the checkout". | The first import of pytest, Hypothesis and PyYAML on a cold environment writes `.pyc` files there (766 bytecode writes on 3.9 and 740 on 3.14 in the first dry run's audit on a fresh environment, none from a test or from cmdkit). | Precompiling the environment, or `PYTHONDONTWRITEBYTECODE`, changes the run; listing every environment path is brittle. Only the import system, pytest or Hypothesis may write there, never a test or cmdkit. |
| pytest's `pytest-cache-files-*` directory in the root is read as part of `.pytest_cache/`. | pytest 8 and later build `.pytest_cache` in that temporary sibling and rename it into place; it is the cache C1 names, mid-creation. | None simpler: the alternative is disabling the cache provider, which C1 rules out. |
| R4's "a test of the other run" sets aside, among the writes made while a test frame is on the stack, the import system's, Hypothesis's (its example database is a C1 cache), and pytest's bookkeeping for its numbered directories (`pytest-of-<user>/`, `pytest-current`, `pytest-N/` and their lock files under the system temporary directory). Everything else a test's code, cmdkit or the standard library writes counts. | pytest creates its numbered directories lazily; a test that first asks for the basetemp makes pytest write that shared bookkeeping while the test runs. It is pytest's, not the test's. | Counting every write under a test frame flags a valid design (a session-scoped directory) on pytest's bookkeeping alone; counting only the test's own frames missed a thread running standard-library code and the `cache` fixture (review finding 4). |
| The audit and concurrent modes run the profile's environment with `python -I write_audit.py run` in place of `python -m pytest`. | The hook has to be installed before pytest starts (How it is shown, 2). `tmpdenied` and `R2` run the profile's own form. | A `sitecustomize` or `PYTHONSTARTUP` hook would need the interpreter's environment changed, and `-I` (needed so no gate file shadows a module) ignores both. |

## 4. Rabbit holes (resolved)

No research fan-out: the appetite is small, the root cause is known (trigger 1 doesn't fire), and
no high-blast-radius path is touched (trigger 2 doesn't). Trigger 3 fires (the deliverable is test
infrastructure, and the write audit is a gate), so an adversarial review ran (below).

- **Which audit events, with what arguments, on 3.9 and 3.14.** Probed on both: `open` carries
  `(path, mode, flags)` for `io.open` and `(path, None, flags)` for `os.open`; `dir_fd` is `-1` for
  none on 3.9 and `None` on 3.14; `shutil.rmtree` removes children through `dir_fd`; `os.replace`
  raises `os.rename`. `os.open(..., dir_fd=)` carries no `dir_fd` in its event, so a relative
  `dir_fd` open would resolve against the working directory; nothing in the suite does that, and
  the selftest covers the routes it does use. The hook ignores its own events (a per-thread guard)
  and stops recording before it writes its log.
- **Collecting the base's node IDs.** Collecting at `b9efaca` imports the old module, which writes
  `/tmp/cmdkit/config`: the thing R2 forbids. The 75 IDs were collected once at plan time, inside a
  sandbox (identical on 3.9 and 3.14), and frozen in `verify/base-nodeids.txt`.
- **The expected file names.** `config.special` is named in two calls but never written: both
  `from_local` and `to_local` raise `NotImplementedError` before opening it. The 13 names in
  `written-names.txt` are the ones the base writes.
- **pytest's writes outside `--basetemp`.** A dry run found three kinds, each folded into the
  deviation table: output capture in the system temporary directory, `.pyc` files in the tool
  environment, and pytest 8's `pytest-cache-files-*`.
- **macOS `mktemp -d` ignores `$TMPDIR`.** The gate passes an explicit template under
  `${TMPDIR:-/tmp}`.
- **R2's precondition.** `/tmp/cmdkit` exists on the maintainer's Mac (left by the old suite;
  last written 2026-11-10). R2 conditions on its absence, so `gate.sh R2` fails closed with that
  message; the operator moves the directory aside before the build. Removing it is a non-goal for
  the cycle's code, not for the host.
- **The syntax-tree check prescribes the form.** `same_behaviour.py ast` accepts exactly a last
  `tmp_path` parameter and `{tmp_path}` in the f-strings. A different valid form (`str(tmp_path /
  …)`, a fixture of the module's own) goes red; that is deliberate, since R5 asks for "only where the
  files live changes", and § 2.1 is the form the build writes.

**Adversarial design review.** One reviewer pass against GOAL, this design and the drafted gates,
with mutants against the gate's own decisions, ran before this plan was committed. Findings and
what changed: § 4.1.

### 4.1 Adversarial review

A fresh reviewer, given the GOAL, this design, the drafted `verify/` and the committed prototype,
attacked the gate with mutants in a worktree of its own. Eleven findings; every one is folded in.

1. **HIGH: the frozen check's anchor.** `git log --grep='^[fix] Plan ...'` matches any line of a
   message, so a later commit quoting the plan subject in its body became the "plan commit": a
   blanked `check` then passed `audit`, and a good tree failed `static`. Now both `gate.sh` and
   `change_set.py` find the plan commit by its subject line alone, and the gate also fails when
   any commit since it touches `verify/`. The mutant (body quote plus a blanked `check`) is red.
2. **MEDIUM: a pytest plugin through `spec/`.** With no `testpaths`, a `conftest.py` under
   `spec/tests-use-tmp-path/` redefined `tmp_path` as one shared directory, and every check passed.
   `change_set.py` now refuses any file under `spec/` that pytest's walk would load. Red.
3. **MEDIUM: write routes the hook missed.** A write through a symlink in `tmp_path`, a hard link
   from it, a fork's child, SQLite, `ctypes`, `chflags`/`setxattr`, `fchmod` on a descriptor, an
   `atexit` callback, a thread writing after `pytest.main`. The hook now follows the last
   component for path-following events, records the link source, resolves descriptors, records
   forks, `sqlite3.connect`, AF_UNIX binds, `ctypes` loads, flags and extended attributes, and keeps
   recording until shutdown, with the surviving thread count logged. Each route is in the canary.
   `os.mkfifo` and `os.mknod` raise no audit event on 3.9 or 3.14 (checked), so they stay a stated
   blind spot.
4. **MEDIUM: cross-run sharing `cross` missed.** pytest's `cache` fixture, a thread running
   standard-library code, SQLite at a fixed path. The attribution rule changed (deviation row 4),
   the `cache` fixture's writes are the test's, and the canary shares a file through a thread.
5. **MEDIUM: the leftover check was a no-op in the sandbox.** `pgrep` and `ps` are refused there,
   and the gate read the refusal as "nothing left". Each run now logs its PID, and the gate checks
   it with `kill -0` (which works in the sandbox; checked).
6. **MEDIUM: R2 was vacuous with `/tmp` denied.** `R2` now requires `/tmp` writable, so `P1` runs
   with the sandbox off, and `tmpdenied` runs `concurrent` too, for R3 and R4 under the denial.
7. **MEDIUM: the row's prose wasn't pinned.** The row may now change only by deleting its exact
   `/tmp` sentence. The mutant that cut the row to its command is red.
8. **LOW: `passed` demanded exact equality** with the frozen IDs; it is now a superset check, and
   `ast` keeps tests from being added.
9. **LOW: pytest's environment variables** passed through; suite runs unset them.
10. **LOW: `change_set.py` edge cases.** A missing or duplicated row, or a commit without
    `AGENTS.md`, no longer reads as "done", and the one-commit walk uses the whole row predicate.
11. **LOW: the canary under-covered its claims.** It now runs with the cache provider on and covers
    `chmod`, `fchmod`, links and `dir_fd` routes (finding 3's list).

Mutants run after the fold, all red where they should be: the base tree (`static`, `audit`,
`concurrent`), the row left alone, tests and row in two commits, the row cut to its command, a
`conftest.py` under `spec/`, a body-quoted plan subject with a blanked `check`, a module-level
directory under `tempfile.gettempdir()` (`static`, `audit`, `concurrent`), one test left on
`/tmp`, relative paths, a dropped assertion operand, a skipped test. A session-scoped
`tmp_path_factory` directory is red on `static` (the prescribed form) and green on `concurrent`,
as it should be: it shares nothing across runs.

## 5. Risks & open questions

- **R2 on the build and review hosts.** `R2` runs with the sandbox off, and `/tmp/cmdkit` must be
  absent; on the maintainer's Mac it exists today. Any unsandboxed run of the old suite (a
  `develop` checkout, or #30's branch until it rebases onto this fix) recreates it, and
  `gate.sh R2` goes red again until it is moved aside. The row-exact check in `change_set.py` keys
  on the sentence as `develop` has it today; #30 leaves that sentence as it is.
- **The one-line conflict with #30.** The uv build cycle rewrites another sentence of the same
  `verify` row. Whichever lands second resolves it: keep #30's wording, without this cycle's last
  sentence. `change_set.py` compares the row with the merge-base's, so it holds after a rebase.
- **A Hypothesis or pytest upgrade** may write somewhere new (another cache file, a different
  capture route). The audit then goes red on a write no test asked for; the fix is a reading for
  the review, not a change to the tests.
- **What the hook can't see:** writes by a spawned process (covered by the spawn rule and the
  root listing, not under `/tmp` or home), by C code below Python's os and io layers that a
  library loads without `ctypes`, by a relative `os.open(..., dir_fd=)`, and by `os.mkfifo` and
  `os.mknod` (no audit event). None of these is in the suite today, and the syntax-tree check
  keeps the tests to the base's calls.
- **Windows** isn't run by any mode here (the gate is POSIX `sh`); the change removes the only
  POSIX path the tests named, and CI runs the suite on Windows.

## 6. Verification strategy

cmdkit is a library with no throwaway-environment helper, so the gate drives the suite itself in
the profile's environment, from an export of HEAD.

- `sh spec/tests-use-tmp-path/verify/gate.sh P1`, with the sandbox off, is P1's `verify:` (9 s
  warm for everything before `R2` in the last dry run on the maintainer's Mac; `R2` adds two suite
  runs of about a second each; a cold uv cache adds the downloads).
- `gate.sh tmpdenied`, with the sandbox on, is R3's native check and R4's under the same denial
  (4 s warm): build runs it once and reports it; review runs it again.
- `gate.sh audit` is the one-off write audit of C2, at build (inside `P1`) and again at review.
- Every mode is dry-run on a prototype (§ 4.1 and the report): green on the fixed tree, red on the
  base and on each mutant.

---

*Backing research: none (lean plan).*
