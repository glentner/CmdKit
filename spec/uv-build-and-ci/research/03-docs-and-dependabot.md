# Research 03: Read the Docs with uv, Dependabot `uv`, docs-lock feasibility

Sources were checked on 2026-11-10. Every claim marked "lab" was run in a throwaway project outside the repo with uv 0.13.7 and check-jsonschema 0.39.0.

## 1. Read the Docs with uv

**Native support exists now, so overriding `build.jobs` is no longer the recommended pattern.** The RTD docs have two relevant pages: "Build customization → Install dependencies with uv" (docs/user/build-customization.rst) and "config-file/v2 → python.install → uv" (docs/user/config-file/v2.rst). They say: "Read the Docs supports uv natively in `python.install`", and "Use `build.jobs` only when you need an advanced uv workflow … such as adding specific arguments to the `uv` command." `build.tools` has no `uv` entry; its options are python, nodejs, ruby, rust and golang. Here is the documented example, verbatim:

```yaml
version: 2

build:
  os: ubuntu-26.04
  tools:
    python: "3.14"

python:
  install:
    - method: uv
      command: sync
      groups:
        - docs

sphinx:
    configuration: docs/conf.py
```

The keys for `method: uv` are:
- `command: sync|pip`, which is required.
- `path`, which is optional.
- `groups: [..] | all`, for sync only.
- `extras: [..] | all`.
- `requirements`, for pip only.

Only **one** `python.install` entry is allowed when `method: uv` is used, and the schema enforces this.

**What RTD actually runs.** This comes from the builder source (readthedocs/doc_builder/python_environments.py and director.py):
- It runs `asdf plugin add uv && asdf install uv latest && asdf global uv latest`, so the build gets the latest uv and the version is not pinned.
- It creates the environment with `uv venv $READTHEDOCS_VIRTUALENV_PATH` and skips RTD's own pip/sphinx bootstrap.
- It sets `UV_PROJECT_ENVIRONMENT=$READTHEDOCS_VIRTUALENV_PATH`, `UV_PYTHON=<venv>/bin/python` and `UV_PROJECT=<checkout>`.
- It runs plain **`uv sync --group docs`**, with no `--frozen` or `--locked`. If `uv.lock` is stale relative to `pyproject.toml`, RTD silently re-locks inside the build and does not fail.
- `sphinx.configuration` still drives the default `build` job (`python -m sphinx …` in that venv). You don't need `build.commands`.

**Choice of OS and Python.** The valid `build.os` values are `ubuntu-22.04`, `ubuntu-24.04`, `ubuntu-26.04` and `ubuntu-lts-latest`. Python goes up to `3.14`. In the lab, the docs group built the real `docs/` tree successfully on **3.12 and 3.13**. 3.14 was not tested. A safe choice is `ubuntu-24.04` with `python: "3.13"`.

**Does it install the project?** Yes. `uv sync` installs the project itself, editable by default with the `uv_build` backend. In the lab, `import cmdkit` resolved to `src/cmdkit/__init__.py`, and `conf.py`'s `cmdkit.__version__` worked.

**`--frozen` vs `--locked`.** `--locked` fails if the lock does not match `pyproject.toml`, which is the right check for CI. `--frozen` installs from the lock without checking it. The native RTD path passes neither flag. To get either behaviour you have two options:
- set `UV_LOCKED=1` or `UV_FROZEN=1` as an environment variable in the RTD project dashboard, where uv honours them. A config-file key for this does not exist.
- use the `build.jobs` override below. It was lab-validated against the schema, and RTD then installs nothing itself:

```yaml
build:
  os: ubuntu-24.04
  tools:
    python: "3.12"
  jobs:
    pre_create_environment:
      - asdf plugin add uv
      - asdf install uv latest
      - asdf global uv latest
    create_environment:
      - uv venv "${READTHEDOCS_VIRTUALENV_PATH}"
    install:
      - UV_PROJECT_ENVIRONMENT="${READTHEDOCS_VIRTUALENV_PATH}" uv sync --locked --group docs
```

**Regression found in the lab: `pkg_resources`.** `sphinxcontrib-details-directive` 0.1.0 (its only release, enabled in `conf.py`) does `__import__('pkg_resources').declare_namespace(...)`.
- Under Poetry/pip on RTD, setuptools was present implicitly.
- `uv venv` plus an exact `uv sync` leaves setuptools out, so the build fails with `No module named 'pkg_resources'`.
- setuptools **82+ removed `pkg_resources`**. In the lab, 81.0.0 has it and 82.0.1 and 84.2.1 do not.
- Fix: add `"setuptools<82"` to the `docs` group. With that change the build succeeded. setuptools 81.0.0 was locked, and its latest release requires Python >=3.10, so uv picks an older one for 3.9.

**Validating locally.** Both of these were lab-tested, including negative cases: a second install entry was rejected as "too long", and a typo in `command` was rejected.
- `uvx check-jsonschema --builtin-schema vendor.readthedocs .readthedocs.yaml` works offline, and its vendored schema already knows `method: uv`.
- Upstream schema: `https://raw.githubusercontent.com/readthedocs/readthedocs.org/main/readthedocs/rtd_tests/fixtures/spec/v2/schema.json`. Use it with `check-jsonschema --no-cache --schemafile <url>`. `--no-cache` avoids writing the user cache dir.

## 2. Dependabot `uv` ecosystem

**Status.** Version updates for `package-ecosystem: "uv"` became GA on 2025-03-13 (GitHub changelog). Security updates for uv followed on 2025-12-16.
- Dependabot updates `pyproject.toml` constraints and `uv.lock`, and the uv docs show a single `uv` entry at `/`.
- The options reference lists Dependabot's bundled uv as **v0.11**, while the lab wrote lock `version = 1, revision = 5` with uv 0.13. A lock written by a newer uv could hit an edge case; watch the first PRs.
- The uv guide still says some use cases are not fully supported.
- `github-actions` uses `directory: "/"`, which covers `.github/workflows`.

**Required keys:**
- `version: 2` and `updates`.
- Per entry: `package-ecosystem`, `directory` (or `directories`) and `schedule.interval`. Intervals are daily, weekly, monthly, quarterly, semiannually, yearly or cron.

**`target-branch`.** Dependabot reads manifests from that branch and opens version-update PRs against it. **Security updates ignore `target-branch` and always use the default branch**, and per-entry options such as labels don't apply to them. The config is read from the **default branch (`master`)**, so it has no effect until merged there.

**Existing PRs.** The open Dependabot branches today are `dependabot/pip/idna-3.15`, `soupsieve-2.8.4` and `tornado-6.5.7`. They are pip/Poetry-lock security PRs on the default branch, which `poetry.lock` removal will supersede.

Here is a minimal file. It passed the lab check against both the builtin and SchemaStore schemas, and a typo `uvv` was rejected:

```yaml
version: 2
updates:
  - package-ecosystem: "uv"
    directory: "/"
    target-branch: "develop"
    schedule:
      interval: "weekly"
  - package-ecosystem: "github-actions"
    directory: "/"
    target-branch: "develop"
    schedule:
      interval: "weekly"
```

Validate it with `uvx check-jsonschema --builtin-schema vendor.dependabot .github/dependabot.yml`, or use `--no-cache --schemafile https://json.schemastore.org/dependabot-2.0.json`.

## 3. Docs-lock feasibility

`requires_python` on PyPI:

| package | floor version (req-py) | latest (req-py) | newest that supports 3.9 |
|---|---|---|---|
| idna | 3.15 (>=3.8) | 3.20 (>=3.9) | 3.20 |
| tornado | 6.5.7 (>=3.9) | 6.6.1 (>=3.11) | 6.5.10 |
| soupsieve | 2.8.4 (>=3.9) | 4.1 (>=3.11.5) | **2.8.4**, exactly the floor (2.9–2.10 need >=3.10) |

**uv does fork.** A lab `uv lock` of the translated docs and dev groups with `requires-python >=3.9,<4.0` produced 5 resolution markers: <3.10, 3.10, 3.11–3.11.5, 3.11.5–3.13 and >=3.13. The locked versions were:
- idna: 3.20, one version for all Pythons.
- tornado: 6.5.10 for <3.11 and 6.6.1 for 3.11 and up.
- soupsieve: 2.8.4 for <3.10, 2.10 for 3.10–3.11.5 and 4.1 for 3.11.5 and up.

Every fork is at or above the three floors, so the floors are satisfiable on 3.9. urllib3 and requests also fork (urllib3 2.6.3 / requests 2.32.5 on 3.9).

**Forcing the floors.** Add `[tool.uv] constraint-dependencies = ["idna>=3.15", "tornado>=6.5.7", "soupsieve>=2.8.4"]`. Constraints apply in every fork. In the lab this resolved with the same versions and fails loudly instead of silently dropping below a floor. Don't use `environments` to drop 3.9: it would narrow the lock below the declared `requires-python`.

## Implications for the design

- Use RTD's native `python.install: [{method: uv, command: sync, groups: [docs]}]` on `ubuntu-24.04` with Python `3.13`. The `build.jobs` override is worth it only if the build must fail on a stale lock (`--locked`). The dashboard env var `UV_LOCKED=1` gets the same effect without the override.
- Add `"setuptools<82"` to the `docs` group, or drop or replace `sphinxcontrib.details.directive`. Otherwise the RTD build breaks on `pkg_resources`.
- Add `[tool.uv] constraint-dependencies` floors for idna, tornado and soupsieve so the advisory floors hold in every Python fork. A test can assert this by parsing `uv.lock`.
- Ship `.github/dependabot.yml` with `uv` and `github-actions` entries targeting `develop`. It only takes effect once merged to `master`, and security PRs still target `master`. Validate both config files in CI or tests with `check-jsonschema` builtins (`vendor.readthedocs`, `vendor.dependabot`).
- Check the lock with `uv lock --check` (or `uv sync --locked`) in CI. RTD's native path re-locks silently, so CI is the place to catch drift.
