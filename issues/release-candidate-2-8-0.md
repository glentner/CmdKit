---
status: unshaped
kind: release
appetite: small
---

# 2.8.0 release candidate

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

2.8.0 gathers every cycle on this roadmap, and consumers pin `cmdkit>=2.7.7` with no upper bound
(`AGENTS.md` § Invariants 1). Whatever ships reaches them on their next install. Before the
maintainer cuts the release, `develop` has to show that it is whole on every supported Python and
breaks no known consumer.

## Why it was deferred

It is the last step; it waits on the rest of the 2.8.0 path.

## Outcome / vision

On `develop`, with every 2.8.0 cycle landed:

- the suite passes on 3.9 to 3.14, in CI and under the release recipe's `gate`;
- HyperShell's own test suite passes against cmdkit from `develop`, in a throwaway environment that
  installs both from source;
- `examples/` run, and the docs build;
- `docs/blog/YYYYMMDD_2_8_0_release.rst` and its `docs/blog/index.rst` entry describe every
  change, each opt-in with how to turn it on and each default fix with what it fixed;
- the tutorial shows the opt-ins.

Then the maintainer releases per the release recipe.

## Sketch of the acceptance criteria

- **R1** — The release recipe's `gate` SHALL pass on `develop`.
- **R2** — HyperShell's test suite SHALL pass with cmdkit installed from `develop`, with the same
  results as against 2.7.7.
- **R3** — The 2.8.0 release notes SHALL name every opt-in and every default fix.

**Test that shows it:** the HyperShell suite run twice in throwaway environments, once against 2.7.7
from PyPI and once against `develop`, with identical pass and fail sets; the gate log.

## Notes

- Waits on every entry before it in `ROADMAP.md`.
- A consumer suite that fails on the candidate stops the release for the maintainer's decision.
- Found by: adoption, 2026-11-10.
