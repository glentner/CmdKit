---
status: unshaped
kind: fix
appetite: small
---

# Tests write only to pytest's temporary directories

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`tests/test_config.py:20-21` sets `TMPDIR = '/tmp/cmdkit/config'` and creates it when the module is
imported. `TestNamespace.test_from_local`, `TestNamespace.test_to_local` and
`TestConfiguration.test_from_local` write fixed file names there (`toml.toml`, `system.toml` …).
So the suite:

- fails at collection wherever `/tmp` isn't writable, as in a sandboxed run;
- races with itself when two Python versions run at once, since both write the same files;
- leaves files behind after every run;
- assumes a POSIX `/tmp`.

## Why it was deferred

Pre-existing on `develop`. Adoption changes no test.

## Outcome / vision

Every test that touches the filesystem uses pytest's `tmp_path` (or `tmp_path_factory`), and the
suite writes nothing outside it.

## Sketch of the acceptance criteria

- **R1** — The suite SHALL create no file or directory outside pytest's temporary directories.
- **R2** — Two runs of the suite started at the same time SHALL share no files.

**Test that shows it:** run the suite with `/tmp/cmdkit` absent and `/tmp` not writable to the run
(a sandbox, or a container with a read-only `/tmp` and `TMPDIR` pointed elsewhere): it passes, and
`/tmp/cmdkit` still doesn't exist. `grep -rn "'/tmp" tests/` is empty.

## Notes

- Every configuration cycle on the roadmap edits `tests/test_config.py`, so this goes first.
- `AGENTS.md` § Factory's `verify` row carries a note about `/tmp`; it goes in the same commit.
- Found by: adoption, 2026-11-10.
