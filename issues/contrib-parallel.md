---
status: unshaped
kind: feature
appetite: big
---

# `contrib.parallel`: rank-aware decorators for applications run under MPI

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

A cmdkit application launched with `mpirun -n 4 app …` runs four copies. Each prints its own output
and writes its own files, unless the application guards every such step by rank itself. Draft PR #14
("Parallel", 2022) proposed `cmdkit.contrib.parallel`, a vocabulary of decorators for this:

- `squash` runs only on the root rank;
- `single` runs on the root rank and broadcasts its result;
- `limit(n)` runs on ranks below `n`;
- `many` runs on many ranks and gathers or broadcasts;
- `guard` refuses to run in parallel;
- `guarantee` requires MPI;
- `rank` and `size` are module properties that fall back to a serial run.

The vocabulary is worth keeping. The draft can't land as written:

- it makes `psutil` a required dependency and detects MPI by inspecting the parent process's name;
- it checks for `mpi4py` with `pkg_resources`, which current setuptools no longer ships;
- its extra is misspelled (`mpi4pi`);
- it controls flow with `assert`, which `python -O` strips;
- it has no tests (its own TODO), and it predates the `src/` layout and the move off `setup.py`.

## Why it was deferred

It is a new contrib module with an optional dependency, not a defect, and nothing on the 2.8.0 path
needs it. Salvaged from #14.

## Outcome / vision

An opt-in `cmdkit.contrib.parallel` behind an `mpi` extra (`mpi4py`), with no required dependency:

- the draft's decorator names and semantics;
- MPI detected from the launcher's environment variables (Open MPI, MPICH/PMI, PMIx) rather than the
  parent process, with an explicit override;
- `importlib.metadata` for the availability check, and no `assert` for control flow;
- every decorator degrading to a plain call in a serial run;
- tests that run serially and, where `mpi4py` and a launcher exist, under `mpirun -n 2`.

## Sketch of the acceptance criteria

- **R1** — WHILE running serially, every decorator SHALL call the function once and return its result.
- **R2** — WHILE running under MPI, `squash` SHALL run the function only on rank 0, and `single` SHALL
  return rank 0's result on every rank.
- **R3** — Importing the module SHALL need neither `mpi4py` nor `psutil` until MPI is used.

**Test that shows it:** a serial test of every decorator. A test under `mpirun -n 2 python -m pytest`,
skipped when `mpi4py` is absent, in which `single` returns rank 0's value on both ranks and `squash`'s
side effect happens once.

## Notes

- Credit: salvaged from #14 by its author, which drew on earlier work in another project. The
  maintainer's review comment there asked that `psutil` not be required for users who don't use the
  module; this design honours it.
- Found by: adoption sweep, 2026-11-10, reading the open draft PRs.
