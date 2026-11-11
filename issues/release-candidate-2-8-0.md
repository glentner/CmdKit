---
status: unshaped
kind: release
appetite: small
---

# 2.8.0 release candidate

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

2.8.0 ships what has landed on `develop` since 2.7.7 (the uv build, the move to `tmp_path`,
`cli-defaults`) plus `config-variant-collision`. Every other open roadmap entry ships in the 2.8.x
patch series. Consumers pin `cmdkit>=2.7.7` with no upper bound (`AGENTS.md` § Invariants 1).
Whatever ships reaches them on their next install. Before the maintainer cuts the release,
`develop` has to show that it is whole on every supported Python and breaks no known consumer.

## Why it was deferred

It is the last step of 2.8.0; it waits only on `config-variant-collision`.

## Outcome / vision

On `develop`, with `config-variant-collision` landed:

- the suite passes on 3.9 to 3.14, in CI and under the release recipe's `gate`;
- HyperShell's own test suite passes against cmdkit from `develop`, in a throwaway environment that
  installs both from source;
- `docs/blog/20261111_2_8_0_release.rst` and its `docs/blog/index.rst` entry describe every change
  in 2.8.0, each default fix with what it fixed, and the docs build. The section on
  `config-variant-collision` is confirmed against the code that landed.

Then the maintainer releases per the release recipe.

## Sketch of the acceptance criteria

- **R1** — The release recipe's `gate` SHALL pass on `develop`.
- **R2** — HyperShell's test suite SHALL pass with cmdkit installed from `develop`, with the same
  results as against 2.7.7.
- **R3** — The 2.8.0 release notes SHALL name every change that ships in 2.8.0, and match the
  landed code.

**Test that shows it:** the HyperShell suite run twice in throwaway environments, once against 2.7.7
from PyPI and once against `develop`, with identical pass and fail sets; the gate log.

## Notes

- Waits on `config-variant-collision` only. The other open entries in `ROADMAP.md` ship in 2.8.x.
- A consumer suite that fails on the candidate stops the release for the maintainer's decision.
- Found by: adoption, 2026-11-10. Retargeted to what has landed plus `config-variant-collision`,
  2026-11-11.
