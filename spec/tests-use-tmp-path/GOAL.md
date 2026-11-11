# GOAL — Tests write only to pytest's temporary directories

> **Origin spec.** The *what* and *why*: the locked contract the review grades against.
> The *how* lives in [`PLAN.md`](PLAN.md) and [`TECH.md`](TECH.md), written by the plan step.
> Edit requirements here; do **not** silently drift them during build.

- **slug:** tests-use-tmp-path
- **kind:** fix
- **appetite:** small

## Problem

`tests/test_config.py` sets `TMPDIR = '/tmp/cmdkit/config'` at lines 20–21 and creates it with
`os.makedirs` when the module is imported. Three tests then write fixed file names there:
`TestNamespace.test_factories` and `TestNamespace.test_from_local` (`toml.toml`, `tml.tml`,
`yaml.yaml`, `yml.yml`, `json.json` and their `.conf` twins), `TestNamespace.test_to_local` (the
same, plus `config.special`), and `TestConfiguration.test_from_local` (`system.toml`, `user.toml`,
`local.toml`). The path has been there since 2dee1ec ("extend unit tests", 2020-06-01); the defect
is pre-existing on `develop`.

So the suite:

- fails at collection wherever `/tmp` isn't writable to the run, as in a sandbox that denies it;
- races with itself when two runs start at once (two Python versions against one checkout, say),
  because both write and delete the same files;
- leaves its files behind after every run;
- assumes a POSIX `/tmp`. On Windows the path resolves to `\tmp\cmdkit\config` on the working
  drive: it passed on the Windows jobs of #30, but only by accident of that drive being writable.

Every configuration cycle on the roadmap edits `tests/test_config.py`, so this one goes first and
stays mechanical: later cycles rebase onto it cleanly.

## Outcome / vision

The suite runs wherever pytest can make its own temporary directory: under a sandbox that denies
`/tmp`, twice at once from one checkout, on Windows without a `\tmp`. Each test that touches the
filesystem works in a directory pytest gives it, nothing is left behind outside pytest's base
temporary directory, and the tests assert exactly what they assert today. The profile's `verify`
row loses its note about allowing `/tmp/cmdkit/config`.

## Acceptance criteria (the contract)

- **R1** — WHEN the suite runs, every file or directory a test creates, writes, renames or removes
  SHALL lie under pytest's base temporary directory (pytest's default, or the one `--basetemp`
  names). The caches the tools keep in the checkout (`.pytest_cache/`, `.hypothesis/`,
  `__pycache__/`) are not files a test writes and fall outside this requirement (C1). Today three
  tests write under `/tmp/cmdkit/config`, and importing `tests/test_config.py` creates it.
- **R2** — WHEN the suite runs with `--basetemp` pointing at a fresh, empty directory, on a POSIX
  host where `/tmp/cmdkit` does not exist, the suite SHALL pass, and `/tmp/cmdkit` SHALL still not
  exist afterwards.
- **R3** — IF `/tmp` is not writable to the run (a sandbox that denies it, with the system
  temporary directory pointed elsewhere), THEN the suite SHALL collect and pass. Today it fails at
  collection.
- **R4** — WHEN two runs of the suite start at the same time from one checkout (for example the
  profile's two Pythons, run side by side), both SHALL pass, and neither SHALL read or write a
  file a test of the other run wrote. The tool caches R1 sets aside are outside this requirement
  too (C1).
- **R5** — Every test node ID collected from `tests/` at `b9efaca` SHALL still be collected and
  pass, and SHALL exercise the same behaviour: the same file names and extensions (`.toml`, `.tml`,
  `.yaml`, `.yml`, `.json`, `.conf`, `.special`), the same calls into cmdkit and the same
  assertions. Only where the files live changes.
- **R6** — `AGENTS.md` § Factory's `verify` row SHALL no longer say that the suite writes to
  `/tmp/cmdkit/config` or that a sandboxed run must allow that path, and the change SHALL land in
  the same commit as the test change.

**How it is shown.**

1. R2's run, on the review host.
2. A write audit of one whole run with `--basetemp` at a fresh directory, run once at build and
   again at review, outside the suite (C2). It works on Linux, macOS and Windows alike: for
   example a Python audit hook (`sys.addaudithook`, available on the 3.9 floor) installed before
   pytest starts, recording every path opened for writing and every path created, renamed or
   removed. Every recorded path lies under that `--basetemp` or inside one of R1's tool caches
   (R1).
3. The profile's `verify`, both Pythons, run inside a sandbox that denies writes to `/tmp` (R3),
   and the same two runs started side by side against one checkout (R4).
4. `grep -rnE "['\"]/tmp" tests/` prints nothing.
5. The node IDs `pytest --collect-only -q` lists at `b9efaca` are all present and passing on the
   branch, and the diff under `tests/` changes where files live and nothing a test asserts (R5).

## Non-goals (no-gos)

- **Anything under `src/`.** In particular `AppContext.default`, which creates directories under
  the user's home: no test reaches `AppContext` today (`tests/` doesn't name it), and the profile's
  throwaway-environment row already says how a future test should.
- **The build files**: `pyproject.toml` (its `[tool.pytest.ini_options]` included), the lockfile,
  `.github/` and `.readthedocs.yaml`. The CI matrix belongs to the uv build cycle (#30).
- **Restructuring the tests**: no renaming, splitting, parametrizing or new test of cmdkit's
  behaviour, beyond what moving the paths needs. Later configuration cycles rebase onto this one.
- **Environment-variable hygiene.** `TestConfiguration.test_from_local` sets and removes `CMDKIT*`
  variables in the test process. That state is per process, so it isn't shared between runs, and
  moving it to `monkeypatch` is not this cycle's change.
- **`tests/test_app.py`'s `NONEXISTENT-FILE`**: `FileApp` opens it relative to the working
  directory, for reading, and expects it to be missing. It writes nothing; it stays as it is.
- **Removing a `/tmp/cmdkit` that earlier runs left on a developer's machine.**
- **The tool caches** in the checkout (`.pytest_cache/`, `.hypothesis/`, `__pycache__/`): nothing
  redirects or disables them (C1).
- **A permanent write guard in the suite.** The write audit is a one-off check at build and
  review, and no follow-up seed is written for a guard (C2).

## Clarifications

Carried from the seed (2026-11-10):

- **Q:** Kind and appetite? — **A:** `fix`, `small`, from the seed's frontmatter (resolved
  2026-11-10).
- **Q:** Does the `verify` note in `AGENTS.md` change here? — **A:** Yes, in the same commit as the
  tests (resolved 2026-11-10; R6).

Raised during shaping:

- **C1 · Q:** Do R1 and R4 cover the caches the tools write in the working directory: pytest's
  `.pytest_cache/`, Hypothesis's example database `.hypothesis/`, and Python's `__pycache__/`? All
  three are gitignored and live inside the checkout, not under `/tmp`. — **A:** No. They are
  excluded from R1 and R4, and the contract covers the files the tests themselves write; nothing
  redirects or disables the caches (resolved 2026-11-10; R1, R4).
- **C2 · Q:** Is the write audit (How it is shown, item 2) a one-off check at build and review, or
  a permanent part of the suite that every CI job runs? — **A:** One-off, at build and at review.
  A permanent guard is not this cycle's scope and gets no follow-up seed (resolved 2026-11-10;
  R1).

## Related materials

- Seed: `issues/tests-use-tmp-path.md`; `ROADMAP.md` Part I, order 2.
- Files: `tests/test_config.py` (lines 20–21, 176–258, 533–557); `AGENTS.md` § Factory, the
  `verify` row.
- The uv build cycle, <https://github.com/glentner/cmdkit/pull/30> (open against `develop`): it
  rewrites another sentence of the same `verify` row, so whichever of the two lands second resolves
  a one-line conflict there.
- pytest's temporary directories: <https://docs.pytest.org/en/stable/how-to/tmp_path.html>.
