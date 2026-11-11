---
status: unshaped
kind: feature
appetite: big
---

# Explicit, governed expansion of `_env` and `_eval`

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

Expansion is lazy and happens on any attribute read (`NSCoreMixin.__getattr__`,
`src/cmdkit/namespace.py:80-103`). That is the documented behaviour, and consumers rely on it. It
also means that anything which calls `getattr` runs `_eval` commands with `shell=True` (`:103`):
`hasattr`, a debugger's inspector, or a Jinja template (`{{ cfg.db.password }}` tries `getattr`
first). No application can make expansion explicit, and none can govern it:

- `_eval` inherits stderr, so a failing command's output goes to the terminal, not into the error.
  A non-zero exit raises `CalledProcessError`, which names neither the key nor the layer.
- `_eval` output is `.strip()`ped of all surrounding whitespace, not only the trailing newline.
- An unset variable named by `_env` silently yields `None` (`:99`).
- No layer can be refused. A project-local file in a repository the user just cloned can run
  commands exactly like the user's own file.

## Why it was deferred

Pre-existing; the default is relied on (`AGENTS.md` § Invariants 1 and 2). Found while evaluating
cmdkit for layered configuration.

## Outcome / vision

An explicit opt-in on `Configuration`. Under it:

- an explicit expansion step runs each `_env`/`_eval` once and returns plain values; attribute access
  no longer runs anything;
- a per-layer policy refuses `_eval` (and optionally `_env`) from named layers, checked over the raw
  layer at load, before anything runs;
- a failing `_eval` raises a `ConfigurationError` subclass naming the key, the layer, the source,
  the exit status and the captured stderr;
- only the trailing newline is stripped from `_eval` output;
- an unset `_env` variable raises, naming the key, the layer and the variable.

Without the opt-in, nothing changes: lazy expansion, inherited stderr, `.strip()`, `None` for an
unset variable.

**Default-change check:** each item above changes what an existing caller sees, so each is opt-in
only. None of them is an outright failure.

## Sketch of the acceptance criteria

- **R1** — WHILE the opt-in is off, attribute access SHALL expand exactly as 2.7.7 does.
- **R2** — WHILE it is on, attribute access SHALL run no command and read no variable after the
  expansion step.
- **R3** — WHEN a layer the policy refuses holds an `_eval` key, loading SHALL raise a
  `ConfigurationError` naming the layer and the key, and SHALL run no command.
- **R4** — WHEN an `_eval` command exits non-zero, the error SHALL contain the key, the layer, the exit
  status and the command's stderr.
- **R5** — `_eval` output SHALL lose only its final newline.
- **R6** — WHEN an `_env` variable is unset, the error SHALL name the key, the layer and the variable.

**Test that shows it:** a `local` layer holding `x_eval = "touch <tmp>/ran"` under a policy that
refuses `_eval` from `local` raises at load, and `<tmp>/ran` doesn't exist. `y_eval = "echo oops >&2;
exit 3"` raises with `oops`, `3`, `y` and the layer in the message. `z_eval = "printf '  a  \n'"`
gives `'  a  '`. A default `Configuration` still expands lazily (the existing tests, unchanged).

## Notes

- Waits on `config-provenance`, which supplies the source in the errors.
- `Namespace.from_yaml` uses `yaml.FullLoader` (`namespace.py:172`), which builds more than plain data.
  A layer that refuses `_eval` may also want `yaml.safe_load`; decide at shaping.
- `config-secret-masking` builds on the expanded values.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11.
