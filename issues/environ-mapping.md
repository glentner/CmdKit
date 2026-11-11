---
status: unshaped
kind: feature
appetite: big
---

# An environment mapping that can reach every key

> **Candidate, not a contract.** The feature step promotes this into `spec/{slug}/GOAL.md`, where
> appetite, non-goals and the R-IDs get negotiated. Do not copy it verbatim.

## Problem

`Environ(prefix)` and `Environ.expand` (`src/cmdkit/namespace.py:414-453`) map variables to keys in
a way that leaves some keys unreachable and mangles others. Each case below was probed on `develop`:

- **The prefix match has no trailing `_`.** `name.startswith(prefix)` (`:419`) captures `APPX=1` for
  prefix `APP`, and it expands to the key `''`.
- **Every `_` splits.** `APP_PROFILE_MAX_NUM_SEQS=64` becomes `profile.max.num.seqs`, so no key that
  contains `_` can be set from the environment.
- **Variants can't arrive.** `APP_DB_PASSWORD_ENV=X` becomes `db.password.env`, not
  `db.password_env`.
- **No exclusions.** A variable such as `APP_CONFIG_FILE`, which applications use to choose a file,
  is read as the key `config.file`.
- **Coercion is lossy** (`_coerced`, `:316-331`): `'007'` → `7`, `'1e3'` → `1000.0`, `''` and
  `'null'` → `None`, `'true'` → `True`. A version string or revision that looks numeric changes
  type. `expand(converter=str)` turns it off, but that's undocumented.

## Why it was deferred

The single-`_` split is the documented default, and consumers rely on it (HyperShell builds its
environment layer with `Environ(prefix='HYPERSHELL').expand()`). Found while evaluating cmdkit for
layered configuration.

## Outcome / vision

Opt-ins on `Environ`, passed through `Configuration.from_local` and `from_context`:

- `__` as the nesting separator, so a single `_` stays inside a key;
- `_env` and `_eval` carried through as variants (`APP_DB__PASSWORD_ENV` → `db.password_env`), obeying
  `config-variant-collision`;
- an exclusion list of variable names;
- under the new mapping, the prefix matched with its `_`;
- coercion that can be turned off, documented;
- `flatten` and `export` inverting the new mapping;
- the exact variable name recorded per key (`config-provenance`).

Default `expand()` is unchanged, byte for byte.

**Default-change check:** capturing `APPX` under prefix `APP` is arguably an outright failure (it
yields the key `''`). Fixing it in the default mapping changes which variables a default `Environ`
holds, so it is fixed only in the opt-in (decided at adoption).

## Sketch of the acceptance criteria

- **R1** — WHILE the `__` separator is on, `APP_PROFILE__MAX_NUM_SEQS=64` SHALL map to
  `profile.max_num_seqs`.
- **R2** — WHILE it is on, `APP_DB__PASSWORD_ENV=X` SHALL map to `db.password_env`.
- **R3** — An excluded variable SHALL contribute no key.
- **R4** — WHILE the new mapping is on, `APPX` SHALL NOT match prefix `APP`.
- **R5** — WHILE coercion is off, every value SHALL stay a string.
- **R6** — WITHOUT the opt-ins, `expand()` SHALL return what 2.7.7 returns for the same environment.

**Test that shows it:** with `APP_PROFILE__MAX_NUM_SEQS=64`, `APP_DB__PASSWORD_ENV=X`,
`APP_CONFIG_FILE=/x`, `APPX=1` and `APP_REV=007` set, the opt-in mapping (`__`, exclude
`APP_CONFIG_FILE`, coercion off) gives `{'profile': {'max_num_seqs': '64'}, 'db': {'password_env':
'X'}, 'rev': '007'}`. The default `expand()` of the same environment equals the 2.7.7 result, pinned
in the test.

## Notes

- Waits on `environ-without-prefix` (same code) and `config-provenance` (records the variable name).
- POSIX shells can't export a name containing `-`, so a hyphenated table is unreachable from the
  environment either way; document it.
- Found by: an evaluation of cmdkit 2.7.7 for layered configuration, 2026-11.
