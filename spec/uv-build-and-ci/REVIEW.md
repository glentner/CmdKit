# REVIEW — Build, lock, test and publish with uv

> Adversarial QA by `code-review`, run in an isolated/clean context (a subagent; where the runtime
> has none, `code-review`'s sequential fallback). The correctness pass grades the branch diff against
> [`GOAL.md`](GOAL.md) + the repo's `AGENTS.md` § Invariants **only** — it does not see
> `PLAN.md`/`TECH.md` (avoids grading-its-own-homework / plan-sycophancy). Every finding cites an
> **executed** command, not an assertion.

- **Reviewed commit:** ced301c750d716d69a562f478149a23c2908e3f1  ·  **Base:** develop  ·  **Date:** 2026-11-10
- **Verdict:** approved
- **Cycle:** 1 of ≤3. Mirrors `review.cycle` in `TECH.md`.

A single fresh reviewer graded the change, with no `debate`. Its inputs were `GOAL.md`, the review
rubric, `AGENTS.md`, the runnable worktree, and the diff and log against `origin/develop` with
`spec/` excluded. It ran no sequential fallback.

**Contract history.** `GOAL.md` has two commits after the shape commit, `8a4fe2b` and `0014a36`.
Both are the clarifications C1–C5, ruled at the GOAL gate before the plan was written. They are not
drift during the build.

## Verification run

- **The profile's `verify`**, sandbox off, exits 0: 75 passed on Python 3.9.25 and 75 passed on
  Python 3.14.6, built through uv_build.
- **The CI step** `uv run --locked python -m pytest -v`, reproduced locally: 75 passed on each Python
  from 3.9 to 3.14.
- **`uv build`** gives one sdist and one `py3-none-any` wheel.
  - The wheel built from the sdist, and one built straight from the tree, are byte-identical (`cmp`).
  - METADATA was compared field by field against the 2.7.7 wheel from PyPI, its sha256 checked
    against PyPI's JSON.
  - A negative control on mutated METADATA caught the planted changes to Requires-Dist,
    Requires-Python and Keywords.
- **The wheel installed in isolation** on 3.9 and 3.14 gives `cmdkit.__version__ == '2.7.7'`.
- **`uv lock --check`** exits 0. A negative control, a version bump in a copy, exits 1.
- **The docs:** `uv run --group docs sphinx-build docs docs/_build/html`, run `--locked` with the
  output redirected, prints "build succeeded" on 3.13, Read the Docs' version, and on the default
  Python. `.readthedocs.yaml` validates against Read the Docs' v2 schema with 0 errors.
- **`uv publish`,** dry-run against an unreachable URL, picks up exactly the 2 distributions.
- **The bump probe,** in a copy: only cmdkit's `version` line in `uv.lock` changes, and the wheel
  import check passes at 2.8.0.
- **The licence classifier:** the wheel's METADATA validates under Warehouse's pinned `packaging` and
  `trove-classifiers`. Warehouse rejects only `License` together with `License-Expression`, and this
  wheel has no `License` field.
- **Orchestrator, R5 and R11:**
  - `gate.sh evidence` at `ced301c` is green: `tests` run 42951303127 on `326d5c1` has all 10 jobs
    at success, with 75 passed in each.
  - `git diff --name-only 326d5c1 ced301c` lists only `spec/` files, so that run covers the reviewed
    tree.

## Requirement → evidence matrix

| R-ID | Implemented by (file/commit) | Verified how | Status |
|------|------------------------------|--------------|--------|
| R1 | `pyproject.toml`, `uv.lock` (b287542) | the built wheel and sdist, field by field against 2.7.7: Name, Requires-Python (parsed), Provides-Extra, Requires-Dist (parsed); the `cmdkit/` files and licence text byte-identical; a negative control (reviewer) | ✅ |
| R2 | `pyproject.toml` (b287542) | every difference falls in the permitted list: Metadata-Version, Home-page carried as a Project-URL, the combined Author-email, License-Expression with License-File, the 3.14 classifier; the sdist's PKG-INFO equals the wheel's METADATA (reviewer) | ✅ |
| R3 | `poetry.lock` removed; `pyproject.toml`, `.github/`, `.readthedocs.yaml` | `grep -i poetry` finds nothing (exit 1); the backend is `uv_build`; `[dependency-groups]` holds `dev` and `docs`, and the only extras are toml and yaml (reviewer) | ✅ |
| R4 | `uv.lock` (b287542, 53643d2) | `uv lock --check` exits 0, with a negative control; idna 3.20, tornado 6.5.10 and 6.6.1, soupsieve 2.8.4, 2.10 and 4.1 (reviewer) | ✅ |
| R5 | `.github/workflows/tests.yml` (326d5c1) | statically, the matrix gives exactly 10 jobs, the triggers are right, the Actions are current majors, Python is uv-managed, the suite is unfiltered and reproduced locally (reviewer); every job green on PR #30, run 42951303127 (orchestrator, `gate.sh evidence`) | ✅ |
| R6 | `.github/workflows/publish.yml` (bcc647d) | release-created trigger, `uv build` then `uv publish` with `UV_PUBLISH_TOKEN` from `PYPI_TOKEN`; the dry run finds 2 distributions (reviewer) | ✅ |
| R7 | `.readthedocs.yaml`, the `docs` group with `setuptools<82` (53643d2) | the schema validates; R7's command builds on 3.13 and on the default Python (reviewer) | ✅ |
| R8 | `.github/dependabot.yml` (53643d2) | `uv` and `github-actions` entries, both with `target-branch: develop` (reviewer) | ✅ |
| R9 | `AGENTS.md` (b287542, 326d5c1) | the `verify` text, `version.source`, `bump.lock` and `bump.files`; the gate covers 3.9–3.14; `uv.lock` on the high-blast list; the Invariants 4 line removed; `verify` and `tests.yml` changed together in 326d5c1 (reviewer) | ✅ |
| R10 | none under `src/` | `git diff origin/develop -- src/` is empty; the installed wheel's `__version__` equals `pyproject.toml`'s (reviewer) | ✅ |
| R11 | none needed | every PR job passed on the first run; `ledger.py --seeds` lists no seeds and no changed test files; the diff touches nothing in `tests/` (orchestrator, reviewer) | ✅ |

**Unmapped changes:** none blocking.
- `permissions: contents: read` in both workflows is hardening.
- The job display `name:` in `tests.yml` is cosmetic.
- `.readthedocs.yaml` moves to ubuntu-24.04 and Python 3.13, the docs build R7 checks.

## Findings

None. One candidate, that PyPI might reject the licence classifier beside `License-Expression` at
release, was refuted with executed evidence (see Verification run).

**Noted for the roadmap step, not a finding:** `ROADMAP.md`'s preamble still says verify "runs under
Poetry's build backend and uv's alike". The file isn't in this diff, and stale docs outside it
belong to `docs-accuracy`.

## Human-gate triggers

None: there are no CONFIRMED findings. The diff touches high-blast-radius paths (`pyproject.toml`,
the lockfile, `publish.yml`), and every change into `develop` is merged by the maintainer.

## Optional completeness sub-pass (separate reviewer; may see TECH.md)

Not run.
