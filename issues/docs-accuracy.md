---
status: unshaped
kind: docs
appetite: small
---

# The documentation states what the code and CI do

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

Claims in the documentation have drifted from the code and CI:

- `docs/index.rst:105` says cmdkit "is tested on Python 3.7+"; the floor is 3.9
  (`requires-python >=3.9`).
- `README.rst` and `docs/index.rst` say it is tested on Windows, macOS and Linux; the `tests` workflow
  runs on Ubuntu only until the uv cycle adds macOS and Windows, which makes the claim true.
- The `Configuration` and `Configuration.extend` docstring examples are missing a closing parenthesis
  (`src/cmdkit/config.py:43-44`, `:81-82`). The `from_context` docstring names the wrong user path;
  `issues/platform-default-paths.md` fixes that one with the code.
- `Environ.reduce` is documented as deprecated (`src/cmdkit/namespace.py:455-457`) but warns nobody.

## Why it was deferred

Pre-existing. Found by the adoption sweep.

## Outcome / vision

Each claim matches the code and the CI matrix. Docstring examples parse. `Environ.reduce` is no
longer called deprecated, and it gains no `DeprecationWarning`: a warning is a default change for
consumers who run with `-W error` (decided at adoption).

## Sketch of the acceptance criteria

- **R1** — The Python floor stated in `README.rst` and `docs/index.rst` SHALL equal `requires-python`.
- **R2** — The platforms named as tested SHALL be those in the `tests` workflow's matrix.
- **R3** — Every `Example:` block in `src/cmdkit` SHALL be syntactically valid Python.

**Test that shows it:** a test reads `requires-python` from `pyproject.toml` and checks the version
stated in both documents. A test parses each `>>>` statement in the package's docstrings with
`ast.parse` (continuations joined). `sphinx-build` exits 0.

## Notes

- Waits on `uv-build-and-ci` (`pyproject.toml`, the CI matrix, `.readthedocs.yaml`).
- Running the docstring examples as doctests would need fixtures for files and the environment; out of
  scope here.
- Found by: adoption sweep, 2026-11-10.
