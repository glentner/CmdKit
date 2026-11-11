# CmdKit: agent notes

`cmdkit` is a small library for building command-line applications in Python: an `argparse`
interface that takes hand-written usage and help text (`Interface`), application and
application-group entry points with exit statuses (`Application`, `ApplicationGroup`), layered
configuration with depth-first merging and `_env`/`_eval` expansion (`Namespace`, `Environ`,
`Configuration`), ANSI helpers, logging styles and platform paths (`AppContext`). It is published
to PyPI as `cmdkit` and documented at <https://cmdkit.readthedocs.io>. Read `README.rst` and
`ROADMAP.md` first.

## Map

- `src/cmdkit/__init__.py`: the public interface (`__all__`), `__version__` read from the installed
  metadata, and the library's `NullHandler`.
- `src/cmdkit/namespace.py`: `NSCoreMixin` (depth-first merge, attribute access, lazy `_env`/`_eval`
  expansion), `Namespace` (file loaders and writers, `whereis`, `duplicates`) and `Environ`
  (environment variables in and out).
- `src/cmdkit/config.py`: `Configuration` (named layers, the `_` layer for in-place changes, `which`,
  `whereis`, `duplicates`) and `ConfigurationError`.
- `src/cmdkit/cli.py`: `Interface`, the `argparse.ArgumentParser` subclass that raises instead of
  exiting, and the process-wide `--version` action override.
- `src/cmdkit/app.py`: `Application`, `ApplicationGroup`, `ExitStatus` and `exit_status`.
- `src/cmdkit/ansi.py`: colour constants, `NO_COLOR`/`FORCE_COLOR`, and `colorize_usage`, the
  highlighter for usage and help text.
- `src/cmdkit/logging.py`: the `NOTICE`, `TRACE` and `DEVEL` levels, `Logger`, `LogRecord` and the
  logging styles.
- `src/cmdkit/platform.py`: `AppContext`, the system, user and local paths per platform.
- `src/cmdkit/contrib/builder.py`: `BuilderNamespace` and `BuilderConfiguration` (`trim`).
- `tests/`: pytest and hypothesis. `docs/`: Sphinx (API, tutorial, and release notes under
  `docs/blog/`). `examples/`: two runnable applications.

## Factory

This repo is built by the spec-driven factory: GOAL → PLAN/TECH → build → blind review → publish. The method and the skills that run it live in the maintainer's own tooling, outside this repo. The cycle's records live here: `spec/{slug}/` for work in flight, `issues/` and `ROADMAP.md` for deferred work. Inside this repo, its own rules win.

### Profile

| Key | Value |
|---|---|
| base | `develop`, the branch every cycle starts from and lands on. `master` is the default branch and the release channel: it moves only at a release, through a `release/<ver>` branch (git-flow) |
| branches | `feature/{slug}`, `fix/{slug}`: the prefix per GOAL `kind`; any other kind takes `feature/`; the set is open |
| commit categories | `[config]` `[env]` `[cli]` `[app]` `[logging]` `[ansi]` `[platform]` `[contrib]` `[tests]` `[build]` `[ci]` `[docs]`: the area a change lands in; the set is open. Branch commits take the GOAL's `kind` verbatim. History before adoption uses plain imperative subjects ("Allow Python 3.9") and stays as it is |
| branch commits | `[{kind}] Build {slug} P<n>`; no trailers, `Co-Authored-By` included |
| landing | `squash-pr`: one PR per cycle from its branch into `develop`, titled `[{category}] {What changed}` and squashed on merge. The maintainer merges every PR |
| ci | `gh pr checks` must be green before landing: the `tests` workflow runs on every PR into `develop` |
| setup | none: `verify` installs the tree into a fresh, isolated environment on every run |
| verify | `(for v in 3.9 3.14; do uv run --isolated --no-project --python $v --with pytest --with hypothesis --with tomli --with tomli-w --with pyyaml --with-editable . python -m pytest || exit 1; done)`: the whole suite on the floor and the newest Python. It installs the tree through uv's build backend. |
| throwaway environment | none: cmdkit is a library and keeps no state of its own. A test that reaches `AppContext.default` passes `create_dirs=False` or a temporary home, because the default creates directories under the user's home |
| coupled core | the configuration core (`src/cmdkit/namespace.py` `NSCoreMixin` and `Environ`, `src/cmdkit/config.py`); the command-line path (`src/cmdkit/cli.py`, `src/cmdkit/app.py`, `colorize_usage` in `src/cmdkit/ansi.py`); the public interface (`src/cmdkit/__init__.py` `__all__` and `docs/api/`); the build (`pyproject.toml`, the lockfile, `.github/workflows/`, `.readthedocs.yaml`) |
| same-commit rules | see § Conventions |
| high-blast-radius paths | see § Invariants |
| security lane | off: cmdkit has no network surface and no credentials of its own. It reads only what the application hands it (its files, its environment, its argv), and running `_eval` commands from configuration is documented behaviour; governing it is public roadmap work (`issues/config-explicit-expansion.md`) |
| release | see Release recipe (`release.trigger`) |

### Release recipe

```yaml
release:
  trigger: on-demand
  version:
    source: pyproject.toml project.version
    scheme: pep440
    tag_format: "{v}"
    prerelease_syntax: '^\d+\.\d+\.\d+(a|b|rc)\d+$'
    propose_next: none
  bump:
    lock: uv lock               # rewrites cmdkit's own entry in uv.lock; a bumped version without it fails `uv lock --check`
    lockstep: []
    files: [pyproject.toml, uv.lock]
    diff_rule: only the version string changes, in pyproject.toml and in cmdkit's own entry in uv.lock
    subject: "[build] Version {v}"
  gate:
    - (for v in 3.9 3.10 3.11 3.12 3.13 3.14; do uv run --isolated --no-project --python $v --with pytest --with hypothesis --with tomli --with tomli-w --with pyyaml --with-editable . python -m pytest || exit 1; done)
    - uv build
    - uv run --isolated --no-project --with dist/cmdkit-{v}-py3-none-any.whl python -c "import cmdkit; assert cmdkit.__version__ == '{v}'"
  tag:
    message: "Release {v}"
    signed: true
  notes: none                   # hand-written: docs/blog/<date>_<v>_release.rst is the source; the GitHub release's title and body come from it
  modes:
    release:
      base: develop
      prerelease: forbidden
      final: true
      inputs: []
      work_branch: release/{v}
      branch_ops: []
      merge_into: master
      tag_on: merge
      back_merge_into: develop
      push: [master, "{v}"]
      publish: gh release create {v} --verify-tag --title "<title>" --notes-file <notes>   # creating the release runs publish.yml, which uploads to PyPI
  post_verify:
    - gh run list --workflow publish.yml --limit 1
    - uv run --isolated --no-project --refresh --with cmdkit=={v} python -c "import cmdkit; print(cmdkit.__version__)"
  caveats:
    release: a GitHub release is a PyPI publish, and a PyPI version can never be reused. Read the Docs builds `latest` from the default branch.
  clean_paths: [dist/, build/, docs/_build/]
```

### Where deferred work goes

A pass that decides not to fix something records it, and the destination is fixed:

| Home | Holds | Written by |
|---|---|---|
| `issues/{slug}.md` | deferred code work, from the `ISSUE.md` template, `status: unshaped` | whoever defers it |
| `ROADMAP.md` | the ordered index: one entry per issue, its `**Seed:**` pointing at the `issues/` file | whoever defers it |
| `spec/{slug}/` | work in flight | the lifecycle skills |
| the operator's harness log, outside this repo | harness friction ("was this the skill's fault?"), as `friction` lines; never code follow-ups | the lifecycle skills |

An `issues/` seed is a candidate, not a contract. The feature step promotes it into `spec/{slug}/GOAL.md`, and that is where appetite, non-goals and R-IDs get negotiated. A seed is never copied into a GOAL verbatim.

## Invariants

The gate for every plan and the footgun list for every review. A plan walks only the sections its change touches. A review grades every violation of a numbered section, lettered subsections included, as CRITICAL; a violation of § Conventions is HIGH.

### High-blast-radius paths (human gate)

A CONFIRMED finding in any of these files needs a human decision before the cycle lands; a plan touching one always runs research. The list only widens: when code moves, add the new home and never remove the old entry. Skills and templates cite this list and never copy it.

- `src/cmdkit/namespace.py` (the merge, attribute expansion that runs shell commands, the environment mapping)
- `src/cmdkit/config.py` (layers, `which`, `ConfigurationError`)
- `src/cmdkit/app.py` (`Application.main`, exception handling, exit statuses)
- `src/cmdkit/cli.py` (`Interface`, and the `argparse` override that reaches every parser in the process)
- `src/cmdkit/logging.py` (the logger class and record factory it installs process-wide)
- `src/cmdkit/__init__.py` (the public interface and everything that runs at import)
- `pyproject.toml` and the lockfile: `uv.lock` (`poetry.lock` until the move to uv)
- `.github/workflows/publish.yml` (the PyPI publish path)

A cycle that adds a module to the public interface, a new process-wide effect, or a new publish path adds its paths here in the same commit.

### 1. Compatibility: 2.x is additive [human gate]

Consumers pin `cmdkit>=2.7.7` with no upper bound (HyperShell pins `cmdkit[toml]>=2.7.7`), so whatever ships next reaches them on their next install.

- Behaviour a consumer can rely on stays the default: lazy attribute expansion of `_env` and `_eval`; `Environ.expand` splitting on every `_`; `Configuration.which` returning a layer label; the `ExitStatus` values; `Interface` taking hand-written usage and help verbatim; every name in a module's `__all__`.
- New behaviour arrives as an explicit opt-in (a keyword or attribute on `Configuration`, `Environ`, `Application` or `Interface`), and its absence leaves today's behaviour byte for byte.
- An outright failure (an exception or a silently wrong value where the documented behaviour has an answer) is fixed by default. A cycle that calls something an outright failure says so in its GOAL and names the test that pinned the old behaviour, if any.
- A change that can't close without changing a default stops for a human decision.
- Every opt-in lands with a test that pins the default unchanged beside the test of the new behaviour.
- A release candidate runs HyperShell's test suite against the candidate before a release.

### 2. Configuration core (`src/cmdkit/namespace.py`, `src/cmdkit/config.py`) [human gate]

- Loading, construction, merging, item access and `dict()` never run an `_eval` command or read an `_env` variable. Only attribute access expands, and only the key asked for.
- A layer handed to `Configuration` is copied in; merging never mutates a layer.
- The merge is depth-first: it descends only where both sides are mappings; anything else replaces.
- In-place changes to a `Configuration` (`update`, attribute assignment) are recorded in its `_` layer, and `which` reports them as `_`.
- `name`, `name_env` and `name_eval` are one key across layers: the highest layer that sets any of them decides.
- Known limitation (recorded, not fixed): item assignment and `setdefault` bypass the `_` layer → `issues/config-local-layer-tracking.md`.

### 3. Command line (`src/cmdkit/cli.py`, `src/cmdkit/app.py`) [human gate]

- `Interface` never exits the process: help, version and errors are raised (`HelpOption`, `VersionOption`, `ArgumentError`).
- `Application.main(cmdline)` returns an `int` from `ExitStatus` and never calls `sys.exit`; an exception it doesn't handle is logged and re-raised.
- A hand-written usage or help text is printed as written, colorized by `colorize_usage` unless colour is off or disabled.

### 4. Footprint

- The Python floor is 3.9 (`requires-python >=3.9`), and CI and the release gate cover every minor version from the floor to the newest.
- No required runtime dependency. TOML writing and pre-3.11 reading come from the `toml` extra, YAML from the `yaml` extra; TOML reading uses the standard library's `tomllib` from 3.11.
- Importing cmdkit adds no process-wide effect beyond those it has today (the `--version` action override, the logger class, the record factory, three level names), and that list only shrinks → `issues/import-side-effects.md`.

### Conventions (same-commit rules)

- Version lives only at the release recipe's `version.source`; the release recipe's `gate` mirrors CI.
- The profile's `verify`, the matrix in `.github/workflows/tests.yml` and the release recipe's `gate` change together.
- A change to public behaviour updates its docstring (with its `Example:` block) and the page under `docs/api/` or `docs/tutorial/` that describes it.
- A release adds `docs/blog/YYYYMMDD_X_Y_Z_release.rst` and its entry at the top of `docs/blog/index.rst`.
- No spec R#/P# ids in source code.
- Point to a rule; don't restate it. A rule restated in N places is a same-commit obligation in all N.
- Prose and commit voice follow this section; voice is hygiene, not a review finding.

#### Code style

New code reads as if the author wrote it alongside `src/cmdkit/`:

- Every source file opens with the SPDX block (`# SPDX-FileCopyrightText: 2022 CmdKit Developers`, `# SPDX-License-Identifier: Apache-2.0`), then the module docstring.
- Imports come in commented groups, in order: `# type annotations` (with `from __future__ import annotations`), `# standard libs`, `# external libs`, `# internal libs`; then `# public interface` and the module's `__all__`.
- Four-space indents, single-quoted strings, type annotations on every public signature.
- A public function or class has a docstring; behaviour worth showing gets an `Example:` block in doctest form.
- Commit subjects are `[area] What changed`: imperative, capitalized, at most 72 characters, no trailing period, no trailers.

#### Contributions

From `README.rst` § Contributions, verbatim:

> Contributions are welcome in the form of suggestions for additional features, pull requests with
> new features or bug fixes, etc. If you find bugs or have questions, open an *Issue* here. If and
> when the project grows, a code of conduct will be provided along side a more comprehensive set of
> guidelines for contributing; until then, just be nice.

From `docs/contributing.rst`, verbatim:

> Development of *cmdkit* happens on `Github <https://github.com/glentner/cmdkit>`_.
> If you find bugs or have questions or suggestions, open an *Issue* on Github.
> Fixes and new features are welcome in the form of *Pull Requests*.
>
> If and when *cmdkit* gains any significant number of additional contributors,
> a code of conduct will be included; until then, just be nice.
