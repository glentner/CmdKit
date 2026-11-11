---
status: unshaped
kind: feature
appetite: small
---

# Masked display of secret values

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

cmdkit has no notion of a secret. `repr(Configuration)` prints every layer raw
(`src/cmdkit/config.py:69-74`), and so do `to_dict` and every writer. Today that is safe only
because expansion is lazy: a layer holds `password_eval = "pass show db"`, not the password. Once
values are expanded explicitly (`issues/config-explicit-expansion.md`), they are plain strings, and
any `repr`, log line or `config show` command prints them.

## Why it was deferred

A feature, and it follows explicit expansion. Found while evaluating cmdkit for layered
configuration.

## Outcome / vision

An opt-in masked view, which a `config show` command or a log line can print safely. In it, every
value produced by `_env` or `_eval` expansion is masked, as is every key the application names as
secret (a list of names or a predicate). The raw values stay reachable. The default `repr` and
`to_dict` are unchanged.

## Sketch of the acceptance criteria

- **R1** — WHEN a configuration is shown through the masked view, every value produced by `_env` or
  `_eval` expansion SHALL be replaced by a fixed mask.
- **R2** — Keys the application declares secret SHALL be masked whatever their source.
- **R3** — Without the opt-in, `repr` and `to_dict` SHALL be unchanged.

**Test that shows it:** expand `token_eval = "echo s3cret"` explicitly; `'s3cret'` doesn't appear in
the masked view's `repr`, while the token's value still reads `'s3cret'`. A key declared secret is
masked even as a plain value.

## Notes

- Waits on `config-explicit-expansion`.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11.
