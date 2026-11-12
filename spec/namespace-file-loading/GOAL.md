# GOAL — File loading accepts paths and handles, and its errors name the file

> **Origin spec.** The *what* and *why*: the locked contract the review grades against.
> The *how* lives in [`PLAN.md`](PLAN.md) and [`TECH.md`](TECH.md), written by the plan step.
> Edit requirements here; do **not** silently drift them during build.

- **slug:** namespace-file-loading
- **kind:** fix
- **appetite:** small

## Problem

`Namespace` reads and writes configuration files through `from_local` and `to_local`, which pick a
loader or writer by extension, and through the per-format methods they dispatch to
(`src/cmdkit/namespace.py:131-240`). `Configuration.from_local` reaches the same loaders for each
layer it is given (`src/cmdkit/config.py:211`). Four failures, each reproduced on `origin/develop`
(`386a09a`) under Python 3.9 and 3.14 with identical results:

```python
# a file with a TOML syntax error, passed as one of several layers
Configuration.from_local(user='/etc/app/bad.toml')
#   TOMLDecodeError: Invalid value (at line 2, column 5)      <- which file?
Namespace.from_json('bad.json')
#   JSONDecodeError: Expecting value: line 1 column 7 (char 6)

Namespace.from_local(pathlib.Path('c.toml'))
#   NotImplementedError: type does not currently support 'toml' files
Namespace.from_toml(pathlib.Path('c.toml'))
#   AttributeError: 'PosixPath' object has no attribute 'read'
Namespace({'a': 1}).to_local(pathlib.Path('c.json'))
#   NotImplementedError: Namespace does not currently support "json" files."

class Sub(Namespace):                     # a loader that fails for its own reasons
    @classmethod
    def from_json(cls, path_or_file, **options): raise AttributeError('inner')
Sub.from_local('c.json')
#   NotImplementedError: type does not currently support 'json' files

Namespace.from_toml(open('good.toml', 'rb'))
#   TypeError: Expected str object, not 'bytes'
```

1. **Decode errors don't name the file.** A user with system, user and local configuration files
   can't tell which one is broken. YAML errors already name the file; TOML and JSON errors don't.
2. **`pathlib.Path` is rejected** by every loader and writer, and through `from_local` and
   `to_local` the failure is misreported as an unsupported format. `ignore_if_missing` with a
   `Path` already works.
3. **`from_local` and `to_local` mask errors.** Any `AttributeError` raised while loading or writing
   becomes `NotImplementedError`. The `from_local` message names `type` instead of the class, and
   the `to_local` message ends in a stray `."`.
4. **A binary TOML handle fails** in `from_toml`, though `tomllib.load` itself requires one. A text
   handle works.

Shaping found a fifth of the same kind: `Namespace({'a': 1}).to_toml(io.StringIO())` raises
`TypeError: string argument expected, got 'bytes'`, while a binary handle works (see C1).

All are pre-existing: the faulty lines date from 3d09f1b (2023-09) and 1c366f7 (2024-12) and shipped
in 2.7.7. Under `AGENTS.md` § Invariants 1 each is an **outright failure**: an exception or a wrong
message where the documented behaviour has an answer. So every fix is the default, not an opt-in.
No test pins the old behaviour: `tests/test_config.py` asserts only that an unsupported extension
raises `NotImplementedError` (`test_from_local`, `test_to_local`), and that stays true. The one
visible change for working code is R3: an exception raised inside a loader no longer arrives as
`NotImplementedError`. That masking is itself the defect (it reports a supported format as
unsupported), and no caller can rely on it without also hiding real errors.

## Outcome / vision

Loading and writing configuration files works with `str` and `os.PathLike` paths and with the
handles each format's library takes. A file that fails to decode raises the same error type as
today, with the decoder's own message, and the message also names the file. An unsupported extension
says which class and which extension; any other error comes through as itself. Nothing else about
loading changes.

## Acceptance criteria (the contract)

- **R1** — WHEN a TOML or JSON file given by path (`str` or `os.PathLike`) fails to decode, through
  `from_toml`, `from_json`, `Namespace.from_local` or `Configuration.from_local`, the raised error
  SHALL:
  - be an instance of the decoder's own error type (`tomllib.TOMLDecodeError` from Python 3.11,
    `tomli.TOMLDecodeError` before it, `json.JSONDecodeError`), and so of `ValueError`;
  - have a message that contains the file's path (`os.fspath(path)`) and the decoder's own message
    (for TOML, "Invalid value (at line 2, column 5)");
  - keep the values of `lineno` and `colno` where the decoder's error carries them.
- **R2** — `Namespace.from_local`, `to_local`, `from_toml`, `from_yaml`, `from_json`, `to_toml`,
  `to_yaml` and `to_json` (and their `tml` and `yml` aliases), and each layer path of
  `Configuration.from_local`, SHALL accept an `os.PathLike` wherever they accept a path string, with
  the same result: the same format chosen by extension or `ftype`, the same contents read or
  written, and the same `ignore_if_missing` behaviour.
- **R3** — IF the loader or writer that `from_local` or `to_local` dispatches to raises, THEN that
  exception SHALL propagate unchanged: the same type, and the same message.
- **R4** — WHEN `from_local` or `to_local` is given an extension (or `ftype`) with no loader or
  writer, it SHALL raise `NotImplementedError` whose message names the class it was called on
  (`Namespace`, or the subclass's own name) and the extension, and never `type`, and does not end in
  a stray quote or period.
- **R5** — `from_toml` SHALL load from a binary handle (`open(p, 'rb')`), and SHALL still load from a
  text handle as it does today.
- **R6** — `to_toml` SHALL write to a text handle (`open(p, 'w')`, `io.StringIO`), and SHALL still
  write to a binary handle as it does today (C1).
- **R7** — Everything else SHALL behave as today: loading from a path string or a text handle, YAML
  errors, the return values, the `**options` each method passes on, and the rule that loading never
  expands `_env` or `_eval` (§ Invariants 2). Every test collected from `tests/` at `386a09a` SHALL
  pass unchanged.
- **R8** — The docstrings of the methods R2 names, and their entries in `docs/api/namespace.rst` and
  `docs/api/config.rst` where those state an argument type, SHALL say that a path may be a `str` or
  an `os.PathLike`, in the same commit as the code (§ Conventions).

**How it is shown.**

1. `[a]\nx = \n` in `tmp_path / 'bad.toml'` and `{"a": }` in `bad.json`: `Configuration.from_local(user=…)`
   and the direct loader each raise the decoder's error type, caught as that type and as
   `ValueError`, with `str(path)` and the original message in it, and `lineno`/`colno` unchanged
   (R1). Run on both Pythons by the profile's `verify`, so `tomli` and `tomllib` are both covered.
2. A `Namespace.from_local(tmp_path / 'c.<ext>')` / `to_local(tmp_path / 'c.<ext>')` round trip for
   all three formats, with and without `ftype`, and `Configuration.from_local(user=tmp_path / …)`
   (R2).
3. A subclass whose `from_json` raises `AttributeError('inner')`, and one whose `to_json` does: the
   same `AttributeError` comes out of `from_local` and `to_local` (R3).
4. `from_local('x.ini')` and `to_local('x.ini')` on `Namespace` and on a subclass: the message names
   the class and `ini`, and not `type` (R4).
5. `from_toml(open(p, 'rb'))` and `from_toml(open(p))` load the same `Namespace` (R5);
   `to_toml(io.StringIO())` and `to_toml(io.BytesIO())` write the same TOML (R6).
6. The profile's `verify`, with `tests/` changed only by additions (R7).

## Non-goals (no-gos)

- **Naming the source of a decode error read from a handle.** R1 covers files given by path; a
  handle's errors are unchanged, since a handle need not have a name.
- **YAML decode errors.** They already name the file.
- **`bytes` paths.** `os.PathLike` and `str` only.
- **New formats or extensions** (`ini`, `.cfg`, …): an unsupported extension still raises
  `NotImplementedError`.
- **Errors other than decoding**: a missing file, a permission error, or an undecodable byte
  sequence (`UnicodeDecodeError`) raise as today.
- **TOML has no null.** `Namespace({'a': None}).to_toml(…)` raises `TypeError` from `tomli_w`. That
  is the format, not a defect, and stays as it is.
- **`Environ` and the environment layer**: `issues/environ-without-prefix.md`, next in the roadmap.

## Clarifications

- **Q:** Kind and appetite? — **A:** `fix`, `small`, from the seed's frontmatter (2026-11-11).
- **Q:** Default or opt-in? — **A:** Default. Each item is an outright failure under § Invariants 1,
  and none is pinned by a test; the seed's Outcome says so and the probe on `386a09a` confirms each
  (2026-11-11; R1–R6).

Raised during shaping, ruled at GOAL sign-off (2026-11-11):

- **C1 · Q:** `to_toml` fails on a text handle (`TypeError`), the mirror of R5 found during shaping.
  Include it in this cycle as R6, or record it as a seed and drop R6? — **A:** Include it as R6:
  the same failure class, in the same file, one method (resolved 2026-11-11; R6).
- **C2 · Q:** Does R1 cover decode errors read from a handle as well as from a path? — **A:** No.
  R1 covers files given by path (`str` or `os.PathLike`); a handle's decode errors are unchanged,
  since a handle need not have a name (resolved 2026-11-11; R1, Non-goals).

Raised by the plan, ruled at PLAN/TECH sign-off (2026-11-11; `PLAN.md` § 3):

- **C3 · Q:** Are `dict`, `env` and `local` extensions "with no loader or writer"? Their
  `from_<ext>` / `to_<ext>` are methods other than file loaders and writers (`x.env` silently loads
  `os.environ`, `x.local` recurses). — **A:** Yes. `from_local` and `to_local` raise R4's
  `NotImplementedError` for them: each is an outright failure in the dispatch R4 rewrites (resolved
  2026-11-11; R4, R7).
- **C4 · Q:** Does R4's "(or `ftype`)" make an unknown `ftype` raise? — **A:** No. An `ftype`
  outside `toml`, `tml`, `yaml`, `yml` and `json` is ignored and the extension decides, as today;
  raising would break working calls such as `ftype='TOML'` (§ Invariants 1). R4 applies wherever an
  `ftype` chooses the format (resolved 2026-11-11; R4, R7).
- **C5 · Q:** Does R4 apply to a missing file with `ignore_if_missing=True`? — **A:** No. The
  existence check stays first, so such a file returns an empty namespace whatever its extension, as
  today; `Configuration.from_local` always passes `True` (resolved 2026-11-11; R4, R7).

## Related materials

- Seed: `issues/namespace-file-loading.md`
- Source: `src/cmdkit/namespace.py:131-240` (`from_local`, the loaders, `to_local`, the writers);
  `src/cmdkit/config.py:194-214` (`Configuration.from_local`)
- Tests: `tests/test_config.py` (`test_from_local`, `test_to_local`)
- Docs: `docs/api/namespace.rst`, `docs/api/config.rst`
- `AGENTS.md` § Invariants 1 (compatibility) and 2 (configuration core); `src/cmdkit/namespace.py` is
  a high-blast-radius path.
