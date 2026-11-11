---
status: unshaped
kind: feature
appetite: small
---

# `contrib.guards`: run an application only as the right user or group

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

Administrative tools built on cmdkit often have to refuse to run unless they are root, a named user,
or in a named group. Each application writes that check itself. Draft PR #15 ("Guards", 2022) proposed
`cmdkit.contrib.guards.authorized(groups=…, users=…, root=…, message=…)`, a decorator for exactly
this. The idea is sound, but the draft can't land as written:

- it enforces each check with `assert`, which `python -O` strips, silently disabling the guard;
- `os.getlogin()` fails without a controlling terminal (cron, systemd, batch jobs), and it names the
  login user rather than the effective one;
- its `KeyError` message refers to an undefined name (`group`), so an unknown group raises `NameError`;
- `grp` is POSIX-only, and the draft has no tests (its own TODO says so);
- it predates the `src/` layout.

## Why it was deferred

It is a new contrib module, not a defect, and nothing on the 2.8.0 path needs it. Salvaged from #15.

## Outcome / vision

An opt-in `cmdkit.contrib.guards` with the draft's interface:

- explicit checks that `-O` can't remove;
- the effective user via `pwd.getpwuid(os.geteuid())`;
- an unknown group named in its error;
- a dedicated exception, which `Application.main` can map to an exit status with a message;
- a clear error on platforms without `pwd` and `grp`;
- tests for every branch.

## Sketch of the acceptance criteria

- **R1** — WHEN the effective user fails any configured check, the guarded call SHALL raise the guard's
  exception with its message and SHALL NOT run.
- **R2** — The checks SHALL hold under `python -O`.
- **R3** — WHEN a named group doesn't exist, the error SHALL name it.

**Test that shows it:** monkeypatch `os.geteuid`, `os.getgroups` and `grp.getgrnam`: a guarded function
runs for an allowed user and group, and raises for others. Run the same test under `python -O` in a
subprocess.

## Notes

- Credit: salvaged from #15 by its author; the interface (intersection across options, union within an
  option) is theirs.
- Found by: adoption sweep, 2026-11-10, reading the open draft PRs.
