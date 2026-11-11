# Research 02 — CI matrix: Actions, runners, Python via uv, platform behaviour

Gathered 2026-11-10 with read-only `gh api` calls and local runs of the suite on macOS (arm64).

## 1. Current Action majors

| Action | Latest release | Floating major tag? | Runtime |
|---|---|---|---|
| `actions/checkout` | v7.0.1 (2026-07-20) | yes, `v7` | node24 |
| `astral-sh/setup-uv` | v10.3.3 (2026-10-28) | **no** (last floating tag is `v7`) | node24 |
| `actions/setup-python` | v7.1.0 (2026-10-22) | yes, `v7` | node24 (not needed with uv) |

- **setup-uv publishes no major or minor tags from v8 on.** Its v8.0.0 notes say so ("You won't be
  able to use `@v8` or `@v8.0` any longer"). Its README pins a full SHA with a version comment. So
  `@v10` does not resolve. Use `astral-sh/setup-uv@v10.3.3`, or the release's SHA with a
  `# v10.3.3` comment. Dependabot's `github-actions` ecosystem updates both forms.
- setup-uv v9 turned off cache pruning by default. v10 sets `enable-cache: auto`, which turns the
  cache off for `release`, `pull_request_target` and `workflow_run` events. Neither change matters
  for `push` and `pull_request`. The default `cache-dependency-glob` includes `**/uv.lock` and
  `**/pyproject.toml`.
- **Node runtime.** Runner notes (actions/runner v2.335.0 and v2.338.0) made Node 24 the default
  on 2026-06-16 and set Node 20's removal for 2026-09-23. The current `tests.yml`
  (`checkout@v2`, `setup-python@v2`) still passes, because the runner forces those actions onto
  Node 24. Every job carries the annotation "Node.js 20 is deprecated … being forced to run on
  Node.js 24: actions/checkout@v2, actions/setup-python@v2" (run 42943481662, develop, 2026-11-11).
  Nothing fails today, but R5 requires current majors anyway.

## 2. Runner images and Python 3.9 via uv

- From the actions/runner-images README: `ubuntu-latest` is `ubuntu-24.04`, `macos-latest` is
  `macos-26` (arm64), and `windows-latest` is `windows-2025` (the VS2026 image). The latest run
  also carries the notice "The ubuntu-latest label will migrate to Ubuntu 26 beginning
  October 19, 2026", so Linux jobs may land on 24.04 or 26.04 while that migration runs. Neither
  matters to uv, which downloads its own CPython.
- uv 0.13.7 (latest, 2026-11-03) still offers downloads of CPython **3.9.25** for
  `linux-x86_64-gnu`, `macos-aarch64` and `windows-x86_64`, and 3.14.10 for all three
  (`uv python list 3.9 --all-platforms --all-arches --only-downloads`). Python 3.9 reaching end of
  life has not removed the builds.
- setup-uv's `python-version` input sets `UV_PYTHON` for the rest of the job. `uv sync` and
  `uv run` then create `.venv` with that version, downloading it if needed. That input is the
  uv-native way to pin a matrix job's Python, and the README's own matrix example uses it. An
  explicit `uv python install` step is unnecessary, and `actions/setup-python` is not needed.
- **Caveat: system interpreters.** uv's default `python-preference` (`managed`) will still use a
  matching system interpreter it finds. Locally, `--python 3.9` picked Apple's `/usr/bin/python3`
  (3.9.6) and not a managed build. GitHub's runners also carry tool-cache Pythons on `PATH`, and on
  Windows in the registry. For a matrix that always tests uv-managed CPython, set
  `UV_PYTHON_PREFERENCE: only-managed` (or pass `--managed-python`) at the job level. The suite
  passes either way, so this is about reproducibility, not correctness.

## 3. The suite on macOS and Windows

Local results on macOS (Darwin arm64) for the whole suite:

| Interpreter | pytest / hypothesis | Result |
|---|---|---|
| 3.14 | latest | 75 passed |
| 3.14.6 | 7.4.4 / 6.170.15 | 75 passed |
| 3.9.6 | 7.4.4 / 6.141.1 | 75 passed |

`/tmp` resolves to `/private/tmp` and is writable on macOS. **macOS: no expected failures.**

**Windows: no test is predicted to fail.** What the suite touches, mechanism by mechanism:

- **`TMPDIR = '/tmp/cmdkit/config'` and `os.makedirs` at import** (`tests/test_config.py`).
  CPython resolves the path against the current drive, as `<drive>:\tmp\cmdkit\config`. The
  runner's user is an administrator, so creating a folder at the drive root succeeds. Every use is
  an f-string `'{TMPDIR}/{name}.{ext}'` with mixed separators, which Windows accepts. No test
  compares path strings. The path does not depend on the step's shell: msys `/tmp` mapping applies
  only to bash-launched tools, not to Python's `os` calls.
- **`_eval` expansion** (`TestNamespace::test_attribute_expand_eval`,
  `TestConfiguration::test_attribute_expand_eval`). `subprocess.check_output('echo foo-bar',
  shell=True)` runs `%COMSPEC% /c echo foo-bar` (`cmd.exe`), which prints `foo-bar\r\n`.
  `namespace.py` applies `.decode().strip()`, which removes the `\r\n` and yields `foo-bar`. The
  output is ASCII, so the UTF-8 decode is safe. The `*_multiple_variants` tests raise before
  anything is evaluated.
- **`_env` and `Environ`.** On Windows `os.environ` upper-cases keys, and every test variable is
  already upper case (`CMDKIT_*`), as is the prefix `CMDKIT`. `os.getenv` lookups are
  case-insensitive anyway. Pass.
- **Encodings and line endings.** The tests write fixtures with `open(..., 'w')` and no
  `encoding=`, so cp1252 is used, which is harmless for ASCII content, and newlines become CRLF.
  `from_toml` reads in binary. tomllib and tomli accept CRLF, since TOML allows it. YAML and JSON
  read in text mode with newline translation. `to_*` writes UTF-8 explicitly. Round-trips compare
  parsed data, not file bytes.
- **`capsys` help and usage comparisons.** pytest's `CaptureIO` uses `newline=""`, so no `\r\n`
  is introduced, and the tests `.strip()` before comparing. Colourisation is decided when
  `cmdkit.ansi` is imported (`isatty()` is false under pytest and in CI). **Risk:** setting
  `FORCE_COLOR` in the workflow environment would colourise `Interface` text and break
  `test_app.py`'s usage and help comparisons. Do not set it.
- **`platform.py`.** No test calls `AppContext`. `os.getuid` and `ctypes.windll` are only reached
  inside `_get_*_paths`. Importing `ctypes` is portable.
- **`cmdkit.__version__`** reads the installed metadata, which `uv sync` and `uv run` provide by
  installing the project.
- **hypothesis.** The strategies are small (argparse round-trips). The only plausible platform
  issue is a `DeadlineExceeded` flake on a slow runner (the default deadline is 200 ms). That risk
  is low and predates this cycle. If it shows up, R11's small-fix path applies:
  `@settings(deadline=None)` in the tests.

None of R11's xfail machinery is expected to be needed. If a Windows job does fail, the first
suspects in order are a drive-root permission on `\tmp`, then the `cmd.exe` echo. Both have
one-line fixes confined to `tests/`.

## 4. Dev pins on Python 3.14

- **pytest `>=7.4.4,<8`** resolves to 7.4.4. On 3.14.6 the whole suite passes with `-W default`
  and no warnings. A deliberately failing assertion still produces the full rewritten explanation,
  so assertion rewriting works without the `ast.Str`/`ast.Num` classes that 3.14 removed
  (pytest 7.4 already emits `ast.Constant`). It also passes on 3.9.
- **hypothesis `>=6.92.6,<7`** works on both ends. A universal `uv lock` of these dev pins with
  `requires-python = ">=3.9,<4.0"` forks hypothesis by interpreter: 6.141.1 (the last release for
  3.9), 6.168.5 and 6.170.15. It locks pytest 7.4.4, pyyaml 6.0.3, which has 3.14 wheels, and
  tomli 2.5.0. No pin change is required.

## 5. Collecting CI evidence (read-only)

Push runs fire only on `develop` and `master`, so a feature branch shows only its PR run
(`event == "pull_request"`, `headBranch` = the PR branch, `headSha` = the PR head commit). Find
the run:

```
gh run list -R glentner/cmdkit --workflow tests.yml --branch <branch> --event pull_request \
  --json databaseId,headSha,event,status,conclusion,createdAt,url -L 5
```

For the post-merge push run, pass `--branch develop --event push`, or `--commit <sha>`. Then
check its jobs:

```
gh run view <id> -R glentner/cmdkit --json conclusion,event,headSha,jobs \
  --jq '{conclusion, event, headSha, jobs: [.jobs[] | {name, conclusion}]}'
```

Assert all of the following:

- `status == "completed"` and `conclusion == "success"` on the run;
- `headSha` equals the pushed commit;
- `.jobs | length == 10` (6 Linux, 2 macOS, 2 Windows);
- every job has `conclusion == "success"`;
- the job names cover every (os, python) pair.

Job names default to `<job-id> (<matrix values…>)`, for example `build (3.12)` today. An explicit
`name: ${{ matrix.os }} / py${{ matrix.python-version }}` makes that check a string match. A
compact alternative is `gh pr checks <n> -R glentner/cmdkit --json name,state,bucket`. To wait,
`gh run watch <id> --exit-status` is also read-only.

## Implications for the design

- Pin `actions/checkout@v7` and `astral-sh/setup-uv@v10.3.3` (full version, or SHA plus comment:
  there is no `@v10` tag). Drop `actions/setup-python`.
- Use an explicit `include:` matrix (or `os × python` with excludes) for the ten jobs:
  `ubuntu-latest` × 3.9–3.14, plus `macos-latest` and `windows-latest` × {3.9, 3.14}. Pass the
  version through setup-uv's `python-version`, and set `fail-fast: false` so one platform's
  failure doesn't hide the others.
- Run `uv sync --locked --group dev` (or just `uv run --locked pytest`; `dev` is a default group)
  and then `uv run --locked pytest`. `--locked` makes CI double as the `uv lock --check` gate.
- Optionally set `UV_PYTHON_PREFERENCE: only-managed` so every job tests uv's CPython and not a
  runner or OS interpreter. Do not set `FORCE_COLOR`.
- Give jobs an explicit `name:` that includes the OS and Python, so the run's job list can be
  asserted directly.
- Expect no R11 seeds. Keep the plan's R11 branch as a contingency only.
