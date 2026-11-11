# CmdKit Roadmap

This document records the work after cmdkit 2.7.7, and the salvaged ideas beyond it. Together it is
a revamp: a uv build, fixes to the configuration core's outright failures, opt-in configuration and
command-line behaviour for applications that need more control, and cleanup of long-standing rough
edges. It breaks no existing use. **2.8.0 ships what has landed on `develop` plus
`config-variant-collision`; every other open entry ships in the 2.8.x patch series.** As
`AGENTS.md` § Invariants 1 rules, 2.x is additive: behaviour a consumer can rely on stays the
default, new behaviour is an explicit opt-in, and outright failures are fixed by default.

This is a **forward-looking index, not an implementation plan.** Each entry states a problem and the
intention behind solving it; the *how* belongs to the plan step. As-built architecture and the
load-bearing invariants live in [`AGENTS.md`](AGENTS.md), which stays ground truth.

Each entry's **Seed** points at an [`issues/{slug}.md`](issues/) file, which carries the evidence in
enough detail that a later session doesn't have to re-derive it. Every seed states cmdkit's behaviour
and names a test that would show it. Seeds are **candidates, not contracts**. The feature step
promotes one into `spec/{slug}/GOAL.md`, and that promotion is where appetite, non-goals and the
R-IDs the review will grade are negotiated. The `status:` field on each seed is the guard:

- `unshaped`: a raw deferral;
- `shaped`: negotiated, not yet accepted into a cycle;
- `adopted:{slug}`: promoted. The roadmap step retires it from this index once its cycle lands on
  `develop`.

Two further values, `declined` and `accepted-behaviour`, close a question without shipping. Those are
listed under *Settled questions* at the end.

**Order is deliberate.** The Parts run in order. Each entry's *Order* is its place in the sequence,
and *Waits on* names the cycles that must land on `develop` first. A cycle waits on another when it
builds on that cycle's behaviour or edits the same files. Every cycle lands as its own PR into
`develop`. While a PR waits for review, the next cycle that doesn't wait on it can proceed, so the
command-line Part can run beside the configuration Parts.

- Part I: the build and the test suite;
- Part II: outright failures in the configuration core, fixed by default;
- Part III: opt-in configuration behaviour, ending with the environment mapping;
- Part IV: the command line, defaults first;
- Part V: the rest, ranked;
- Part VI: the 2.8.0 release candidate, which waits only on `config-variant-collision`;
- Beyond 2.8.0: salvaged contrib modules, which 2.8.0 doesn't wait on.

The build is uv throughout. The uv build, the move to `tmp_path` and `cli-defaults` have landed, so
no remaining cycle waits on them: `config-variant-collision` waited on the move to `tmp_path`,
`docs-accuracy` on the uv build, whose files it edits, and most of Part IV on `cli-defaults`.

---

# Part I — Build and tests

Shipped: the build, lock, tests and publish moved to uv (#30), and the suite writes only to pytest's
temporary directories (#31).

## `test_app_invalid_options` stops generating prefixes of `--help`

The test draws random long options and expects each to be an argument error, but argparse takes
`--he` as `--help`, so the suite fails now and then with no change to the code. Skip the prefixes
of the defined long options.

*Order: unset (filed during the cli-defaults cycle) · Waits on: nothing · Refs: —*
**Seed:** [`issues/test-invalid-options-help-prefix.md`](issues/test-invalid-options-help-prefix.md)

---

# Part II — Configuration: outright failures, fixed by default

## A value and its `_env` and `_eval` variants are one key across layers

`token` in one layer and `token_env` in a higher one both survive the merge. Attribute access then
raises "more than one variant", and item access returns the stale lower value. The highest layer
that sets any variant should win.

*Order: 3 · Waits on: nothing (`tests-use-tmp-path` landed, #31) · Refs: —*
**Seed:** [`issues/config-variant-collision.md`](issues/config-variant-collision.md)

## File loading accepts paths and handles, and its errors name the file

TOML and JSON decode errors don't name the file. `pathlib.Path` is rejected and reported as an
unsupported format. `from_local` masks errors raised inside a loader. A binary TOML handle fails.

*Order: 4 · Waits on: `config-variant-collision` (`namespace.py`) · Refs: —*
**Seed:** [`issues/namespace-file-loading.md`](issues/namespace-file-loading.md)

## `Environ.expand` works without a prefix

`Environ().expand()`, `Namespace.to_env().expand()` and `Configuration.from_local(env=True)` without
a prefix all raise `TypeError`.

*Order: 5 · Waits on: `namespace-file-loading` (`namespace.py`) · Refs: —*
**Seed:** [`issues/environ-without-prefix.md`](issues/environ-without-prefix.md)

## Every in-place change to a `Configuration` lands in its `_` layer

Item assignment and `setdefault` bypass the `_` layer, so `which` names the wrong layer or none.
Mutable values are shared between a layer and the merged view.

*Order: 6 · Waits on: `config-variant-collision` (`config.py`) · Refs: —*
**Seed:** [`issues/config-local-layer-tracking.md`](issues/config-local-layer-tracking.md)

## The merged view and `which` agree on where `_` sits

A layer added with `extend` after an in-place change wins in the merged view, while `which` still
names `_`. The value and its label disagree.

*Order: after 6, unranked · Waits on: `config-variant-collision`, `config-local-layer-tracking`
(`config.py`) · Refs: —*
**Seed:** [`issues/configuration-layer-order.md`](issues/configuration-layer-order.md)

---

# Part III — Configuration: opt-in behaviour

## Each value knows where it came from

Record each leaf's source at load (layer plus file path, variable name or flag) and expose it through
a new accessor. `which` keeps returning a label.

*Order: 7 · Waits on: `config-variant-collision`, `namespace-file-loading`, `environ-without-prefix`,
`config-local-layer-tracking` · Refs: —*
**Seed:** [`issues/config-provenance.md`](issues/config-provenance.md)

## Explicit, governed expansion of `_env` and `_eval`

As an opt-in: expand once, explicitly; refuse `_eval` from named layers; capture stderr into errors
that name the key, layer and source; strip only the trailing newline; report an unset `_env`. Lazy
expansion stays the default.

*Order: 8 · Waits on: `config-provenance` · Refs: —*
**Seed:** [`issues/config-explicit-expansion.md`](issues/config-explicit-expansion.md)

## Masked display of secret values

An opt-in masked view in which every expanded value, and every key named secret, is masked. The
default `repr` stays as it is.

*Order: 9 · Waits on: `config-explicit-expansion` · Refs: —*
**Seed:** [`issues/config-secret-masking.md`](issues/config-secret-masking.md)

## An environment mapping that can reach every key

Opt-ins on `Environ`: `__` nesting so `_` stays inside keys, `_env`/`_eval` carried through, an
exclusion list, the prefix matched with its `_`, and coercion that can be turned off. The single-`_`
split stays the default.

*Order: 10 · Waits on: `environ-without-prefix`, `config-provenance` · Refs: —*
**Seed:** [`issues/environ-mapping.md`](issues/environ-mapping.md)

---

# Part IV — Command line

Shipped: with no logging configured, argument errors reach stderr instead of being dropped (#33).

## A group with `ALLOW_NOARGS` can show its help when run bare

Moved out of `cli-defaults`. A bare run of a group that requires its command shows its help and
exits 0 under the opt-in; every other run, `main(None)` with arguments in `sys.argv` among them,
stays exactly as in 2.7.7. Decide on the effective command line, inside `main`'s handling.

*Order: unset (filed during the cli-defaults cycle) · Waits on: nothing (`cli-defaults` landed, #33)
· Refs: —*
**Seed:** [`issues/group-noargs-help.md`](issues/group-noargs-help.md)

## The argument-error report follows `Logger.handle` when filters keep state

The report asks `cmdkit.app`'s filters about a record it builds, and never asks `lastResort`'s, so a
filter that keeps state, reads caller fields or lowers the level can make it differ from Python.

*Order: unset (filed during the cli-defaults cycle) · Waits on: nothing (`cli-defaults` landed, #33)
· Refs: —*
**Seed:** [`issues/last-resort-filter-fidelity.md`](issues/last-resort-filter-fidelity.md)

## `import cmdkit` works when the process has no stderr or stdout

`ansi.py` calls `isatty()` on `sys.stdout` and `sys.stderr` at import, so when either is `None` (a
closed descriptor at startup, `pythonw`) importing cmdkit raises `AttributeError`. Pre-existing in
2.7.7.

*Order: unset (filed during the cli-defaults cycle) · Waits on: nothing · Refs: —*
**Seed:** [`issues/import-without-stderr.md`](issues/import-without-stderr.md)

## An unknown command suggests the closest ones

`unrecognized command: 'confg' (did you mean 'config'?)` on every supported Python.

*Order: 12 · Waits on: nothing (`cli-defaults` landed, #33) · Refs: —*
**Seed:** [`issues/cli-command-suggestions.md`](issues/cli-command-suggestions.md)

## Importing cmdkit leaves other parsers' `--version` alone

`import cmdkit` patches `argparse`'s version action for the whole process, so any plain parser's
`--version` raises cmdkit's exception. Scope the override to `Interface`. The logging globals are
recorded and stay.

*Order: 13 · Waits on: nothing · Refs: —*
**Seed:** [`issues/import-side-effects.md`](issues/import-side-effects.md)

## Hand-written help stays first-class; argparse's generated help is the fallback

Hand-written usage and help keep cmdkit's colorization, unchanged. An application that supplies none
gets argparse's generated help, coloured by argparse where recent Pythons can. Golden tests of today's
output come first.

*Order: 14 · Waits on: `import-side-effects` (`cli-defaults` landed, #33) · Refs: —*
**Seed:** [`issues/argparse-help-fallback.md`](issues/argparse-help-fallback.md)

## A group's own exception handlers never swallow its command's exit status

A group subclass that defines `exceptions` loses its command's exit status. The shared
`Application.exceptions` table stays the default; an explicit opt-in isolates a class's own table.

*Order: 15 · Waits on: `cli-command-suggestions` (`cli-defaults` landed, #33) · Refs: —*
**Seed:** [`issues/app-exception-handlers.md`](issues/app-exception-handlers.md)

---

# Part V — The rest

## cmdkit's log record factory wraps the one already installed, with a test for #20

#20's fix holds but has no test. cmdkit's record factory still discards any factory installed before
it, which the issue's discussion left open.

*Order: 16 · Waits on: nothing · Refs: #20*
**Seed:** [`issues/logging-record-factory.md`](issues/logging-record-factory.md)

## A path accessor that no method name can shadow

Keys named `items`, `keys`, `local` or `namespaces` are unreachable by attribute. An additive path
accessor reaches any key and expands variants as attribute access does.

*Order: 17 · Waits on: `config-explicit-expansion` · Refs: —*
**Seed:** [`issues/namespace-attribute-shadowing.md`](issues/namespace-attribute-shadowing.md)

## Default paths: an XDG layout on request, and the platform edges fixed

An opt-in XDG layout on every POSIX platform, a clear error for a missing Windows variable, and a
docstring that names the real paths. The default layouts and `create_dirs=True` stay.

*Order: 18 · Waits on: nothing · Refs: —*
**Seed:** [`issues/platform-default-paths.md`](issues/platform-default-paths.md)

## `BuilderConfiguration.trim` handles the `_` layer, and can drop a key from every layer

A nested duplicate in `_` raises `KeyError: '_'`, and `ordered=True` works by accident. Add the
module TODO's new-like configuration without a key.

*Order: 19 · Waits on: `config-local-layer-tracking` · Refs: —*
**Seed:** [`issues/builder-trim-local-layer.md`](issues/builder-trim-local-layer.md)

## The documentation states what the code and CI do

Fix the stale Python floor, broken docstring examples, and a deprecation notice on `Environ.reduce`
that nothing enforces (the docs change; no warning is added). The tested-platforms claim is true now
that CI covers macOS and Windows; tie it to the CI matrix.

*Order: 20 · Waits on: nothing (`uv-build-and-ci` landed, #30) · Refs: —*
**Seed:** [`issues/docs-accuracy.md`](issues/docs-accuracy.md)

---

# Part VI — Release candidate

## 2.8.0 release candidate

The suite on 3.9–3.14, HyperShell's suite against `develop` in a throwaway environment, and the
2.8.0 release notes (`docs/blog/20261111_2_8_0_release.rst`). Then the maintainer releases. The
entries left open in Parts I–V follow in 2.8.x.

*Order: 21 (ships ahead of the open entries) · Waits on: `config-variant-collision` · Refs: —*
**Seed:** [`issues/release-candidate-2-8-0.md`](issues/release-candidate-2-8-0.md)

---

# Beyond 2.8.0 — salvaged contrib modules

Ideas from the 2022 draft PRs, rewritten so they can land. 2.8.0 doesn't wait on them.

## `contrib.guards`: run an application only as the right user or group

The `authorized` decorator from #15, with checks that `python -O` can't strip, the effective user,
and tests.

*Order: after 2.8.0 · Waits on: nothing · Refs: #15*
**Seed:** [`issues/contrib-guards.md`](issues/contrib-guards.md)

## `contrib.parallel`: rank-aware decorators for applications run under MPI

The decorator vocabulary from #14 (`squash`, `single`, `limit`, `many`, `guard`), behind an `mpi`
extra, with no required dependency and with launcher detection from the environment.

*Order: after 2.8.0 · Waits on: nothing · Refs: #14*
**Seed:** [`issues/contrib-parallel.md`](issues/contrib-parallel.md)

---

# Settled questions

None yet.
