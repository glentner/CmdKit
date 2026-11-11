# Research digest — uv-build-and-ci

Fan-out (2026-11-10): three read-only briefs, plus the planner's own probes of the build backend
and the 2.7.7 baseline, run in a throwaway prototype worktree at `origin/develop`.

- [`01-pypi-licence-and-publish.md`](01-pypi-licence-and-publish.md): PyPI's licence-metadata
  rules, uv_build's licence forms, `uv publish` with a token, setup-uv's tags.
- [`02-ci-matrix.md`](02-ci-matrix.md): current Action majors, runner images, Python 3.9 under
  uv, the suite on macOS and Windows, the pytest pin on 3.14, reading CI evidence.
- [`03-docs-and-dependabot.md`](03-docs-and-dependabot.md): Read the Docs with uv, dependabot's
  `uv` ecosystem, the lock floors.

## Consolidated decisions

1. **Licence encoding.** `license = "Apache-2.0"` with `license-files = ["LICENSE"]` is the only
   uv_build form that ships the licence text in the wheel (`.dist-info/licenses/LICENSE`); both
   table forms ship none, and a table plus `license-files` fails the build (01, confirmed by the
   planner's probe). The result is `Metadata-Version: 2.4`, `License-Expression: Apache-2.0`,
   `License-File: LICENSE`: GOAL R2 item 4.
2. **The licence classifier stays.** uv_build 0.13.7 warns about `License :: OSI Approved ::
   Apache Software License` beside an expression but builds; PyPI's upload validation rejects only
   `License` together with `License-Expression`, not a licence classifier (01). R2 item 5's
   condition ("only if the build backend refuses it") is not met, so the classifier is kept and the
   gate requires it.
3. **What uv_build writes, against 2.7.7** (planner's probe, uv 0.13.7):
   `Metadata-Version: 2.4`; no `Home-page` (the URL is `Project-URL: Homepage, …`); both
   `Author: Geoffrey Lentner` (2.7.7's value) and `Author-email: Geoffrey Lentner
   <glentner@purdue.edu>`; `Requires-Python: >=3.9, <4.0` (a space after the comma);
   `Requires-Dist` with single-quoted markers; the description identical to 2.7.7's except that
   poetry-core's body ends with one more newline. Directory entries (`cmdkit/`, `cmdkit/contrib/`)
   appear in the wheel's zip listing. Every other field is byte-equal. uv writes a `.gitignore` into
   the build output directory.
4. **Lock floors hold without constraints.** The universal lock forks by Python, and every branch
   is at or above the floors: idna 3.20; tornado 6.5.10 and 6.6.1; soupsieve 2.8.4 (3.9, the
   newest release that supports it), 2.10 and 4.1 (03, planner's lock). No `[tool.uv]` constraint
   is added; the gate checks every locked version.
5. **Docs need `setuptools<82`.** `sphinxcontrib-details-directive` imports `pkg_resources`, which
   an exact uv environment lacks and setuptools 82 removed; with the pin, R7's command and an
   emulated Read the Docs install both build (03; the planner's mutant without the pin fails R7).
6. **Read the Docs uses its native uv install** (`python.install: method: uv, command: sync,
   groups: [docs]`), on `ubuntu-24.04` and Python 3.13 (tested), with no `build.jobs` override. It
   runs `uv sync` without `--locked`, so a stale lock re-locks there; the gate and CI's `--locked`
   catch a stale lock first (03).
7. **Actions.** `actions/checkout@v7` (floating major tag exists). `astral-sh/setup-uv` is at
   v10.3.3 and has published no floating major tag since v8, so it is pinned to the full version tag
   (01, 02). No `actions/setup-python`: setup-uv's `python-version` input installs Python with uv,
   and `UV_PYTHON_PREFERENCE: only-managed` keeps a runner's preinstalled Python out (02).
8. **The suite on macOS and Windows.** 75/75 pass on macOS (3.9, 3.14). Windows is predicted to
   pass (`\tmp\cmdkit\config` is creatable; `cmd.exe`'s echo output is stripped). R11 stays a
   contingency in the plan (02).
9. **pytest 7.4.4 and hypothesis work on 3.14**; the dev pins translate unchanged (02, and the
   prototype's suite on 3.9–3.14).
10. **CI evidence needs a PR.** The `tests` workflow runs on pushes to `develop`/`master` and PRs
    into `develop`, so a pushed feature branch alone starts no run; the evidence comes from the
    cycle's PR run, read with `gh pr list`, `gh run list`, `gh run view --json jobs` and per-job
    `--log` (02). The planner checked these calls' shapes against a real run.
11. **Publish.** `uv publish` with `UV_PUBLISH_TOKEN: ${{ secrets.PYPI_TOKEN }}` in the step's
    environment; with a token set uv skips trusted publishing, so no `id-token` permission. It
    uploads `dist/*` by default; `--dry-run` checks the files without uploading (01).
12. **Dependabot.** `uv` and `github-actions`, `directory: "/"`, `target-branch: "develop"`, weekly;
    both schemas accept it. Security updates ignore `target-branch` and the file takes effect once
    it reaches the default branch (03): residual risk, recorded in PLAN.

## Contradictions resolved

- Read the Docs Python: brief 03's sample file names `ubuntu-26.04`/3.14, its lab built on
  3.12/3.13. Decision: `ubuntu-24.04` and 3.13, the tested pair.
- uv version in workflows: 01 suggests pinning uv `0.13.7` in setup-uv. Decision: not pinned. The
  build backend is pinned in `pyproject.toml` (`uv_build>=0.13.7,<0.14.0`), a newer uv reads the
  lock, and dependabot's `github-actions` updates do not reach a `version:` input.

## Questions raised (all carried by the design)

None needs the GOAL changed. The readings the design takes are PLAN § 3's deviation rows:
`Requires-Python` as a specifier set, the description's trailing newline, `Author` kept beside
the combined `Author-email`, the licence classifier kept, setup-uv's full-version pin as its
current major, the draft PR for CI evidence, and `poetry.lock` kept on the high-blast-radius list.
