---
status: unshaped
kind: feature
appetite: small
---

# Default paths: an XDG layout on request, and the platform edges fixed

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`AppContext.default` (`src/cmdkit/platform.py:47-81`) picks paths per platform:

- **macOS.** User configuration goes to `~/Library/Preferences/<name>/config.toml`, and the
  system's to `/Library/Preferences/…`. Command-line tools on macOS mostly use `~/.config`.
- **Linux and other POSIX.** `~/.<name>/config.toml`; `XDG_CONFIG_HOME` and `XDG_STATE_HOME` are
  ignored.
- **Directory creation.** `create_dirs=True` is the default here and in
  `Configuration.from_context` (`src/cmdkit/config.py:122`), so every call creates `lib` and `log`
  directories under the user's home.
- **The local site** `.<name>` resolves against `CWD`, captured when cmdkit is imported
  (`platform.py:25`), not when `default` is called.
- **Windows.** An unset `ProgramData` or `AppData` makes `os.path.join(None, …)` raise `TypeError`
  (`platform.py:130-131`).
- **Docs.** The `from_context` docstring says the user file is `~/.myapp.toml` (`config.py:136-138`);
  the code gives `~/.myapp/config.toml`.

## Why it was deferred

The paths and `create_dirs=True` are defaults consumers rely on. Found while evaluating cmdkit for
layered configuration (paths) and by the adoption sweep (the rest).

## Outcome / vision

- **Opt-in:** an XDG layout on every POSIX platform, macOS included, honouring `XDG_CONFIG_HOME` and
  `XDG_STATE_HOME`.
- **By default:** a missing Windows variable raises an error naming it, and the docstring states the
  real path.
- **Unchanged:** the default layouts and `create_dirs=True`.

**Default-change check:** resolving the local site against the current directory at call time,
rather than at import, would change where an application that `chdir`s after import looks. Decide
at shaping; this seed records it.

## Sketch of the acceptance criteria

- **R1** — WHILE the XDG layout is chosen, the user configuration SHALL be
  `$XDG_CONFIG_HOME/<name>/config.<ext>`, with `XDG_CONFIG_HOME` defaulting to `~/.config`.
- **R2** — WITHOUT it, every path SHALL equal 2.7.7's on the same platform.
- **R3** — WHEN `ProgramData` or `AppData` is unset on Windows, `default` SHALL raise an error naming
  the variable.
- **R4** — The `from_context` docstring SHALL name the paths the code uses.

**Test that shows it:** monkeypatch `HOME` and `XDG_CONFIG_HOME` to `tmp_path` subdirectories;
`AppContext.default('app', create_dirs=False, layout='xdg').path.user.config` is
`<xdg>/app/config.toml`. The default layout's paths are pinned per platform by patching
`platform.system`. A Windows path test with `AppData` unset raises.

## Notes

- Waits on nothing in the configuration core. `from_context` gains a keyword in `config.py`, so it
  rebases on whichever configuration cycle is open.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11, and the adoption sweep,
  2026-11-10.
