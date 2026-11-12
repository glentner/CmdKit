# PLAN — File loading accepts paths and handles, and its errors name the file

> **Status:** Draft for review · **Last updated:** 2026-11-11
> **Authoritative technical design.** The *how*. Vision/contract is [`GOAL.md`](GOAL.md);
> the phased executable roadmap is [`TECH.md`](TECH.md). Backing detail is in
> [`research/`](research/). Every design element traces to a GOAL R-ID.

## 1. Summary

A local fix to `Namespace`'s loaders, writers and their dispatch in `src/cmdkit/namespace.py`, with
an annotation and a docstring in `src/cmdkit/config.py`. Each loader and writer admits
`os.PathLike` where it admits `str`; `from_local` and `to_local` decide whether a format is
supported before calling it, so nothing a loader raises is caught; the TOML handle branches take
both kinds of handle; and a TOML or JSON file given by path that fails to decode re-raises the
decoder's own error with the path at the head of its message. Two phases: paths, handles and
dispatch first, then decode errors, which lean on the first for `os.PathLike` paths. No new public
name, no new dependency, no opt-in: each item is an outright failure (§ Invariants 1).

## 2. Design

All code changes are in `src/cmdkit/namespace.py`, except § 2.6. Lines not named here stay as they
are, character for character.

### 2.1 Paths (R2)

The six `isinstance(path_or_file, str)` tests in `from_yaml`, `from_toml`, `from_json`, `to_yaml`,
`to_toml` and `to_json` become `isinstance(path_or_file, (str, os.PathLike))`. Nothing else in a
path branch changes: `open` takes an `os.PathLike`, and the `**options` go where they go today.
`from_local` and `to_local` need no path code: `os.path.splitext` and `os.path.exists` take one
already, and they failed only because the masked `AttributeError` (§ 2.2) hid the loader's own
failure. Annotations: `filepath: Union[str, os.PathLike]` on `from_local` and `to_local`;
`path_or_file: Union[str, os.PathLike, IO]` on the six methods. The aliases (`from_tml`, `from_yml`,
`to_tml`, `to_yml`) are the same function objects.

### 2.2 Dispatch (R3, R4)

A module-level constant after `T = TypeVar('T')`, with a comment line:
`_NOT_FILE_FORMATS = ('dict', 'env', 'local')`, the extensions whose `from_<ext>` / `to_<ext>` is a
method other than a file loader or writer (`from_dict`, `from_env`, `from_local` and their `to_`
mirrors). In `from_local`, after the `ignore_if_missing` early return (which stays first, as today):

```python
if ext in _NOT_FILE_FORMATS or not hasattr(cls, f'from_{ext}'):
    raise NotImplementedError(f'{cls.__name__} does not currently support \'{ext}\' files')
return getattr(cls, f'from_{ext}')(filepath, **options)
```

In `to_local`, the same shape, with support decided on the class, and the call made through the
instance as today:

```python
if ext in _NOT_FILE_FORMATS or not hasattr(type(self), f'to_{ext}'):
    raise NotImplementedError(f'{self.__class__.__name__} does not currently support "{ext}" files')
return getattr(self, f'to_{ext}')(filepath, **options)
```

No `try` remains in either, so an exception from the loader or writer propagates as itself (R3).
`cls.__name__` names the class `from_local` was called on, a subclass included; the `to_local`
message loses its stray `."` (R4). Deciding on `type(self)` matters: on the instance, a missing
`to_<ext>` falls through to `NSCoreMixin.__getattr__`, which reads the namespace's own `to_<ext>`
key or expands its `to_<ext>_env` / `to_<ext>_eval` variant (a probe ran the shell command). Once the
class has the method, `getattr(self, ...)` finds it by normal lookup and never reaches
`__getattr__`. The `ftype` tuple, the extension rule and the existence check are unchanged. A
subclass's own `from_<ext>` / `to_<ext>` still works through the dispatch.

### 2.3 TOML handles (R5, R6)

`from_toml`, handle branch:

```python
data = path_or_file.read()
return cls(toml.loads(data.decode() if isinstance(data, bytes) else data))
```

This is what `tomllib.load` does (`b.decode()`, strict UTF-8), so a binary handle loads exactly as
the same file by path, and a text handle (or any object whose `read` returns `str`) as today.

`to_toml`, handle branch, with `import io` added under `# standard libs`:

```python
elif isinstance(path_or_file, io.TextIOBase):
    path_or_file.write(toml.dumps(self.to_dict(), **kwargs))
else:
    toml.dump(self.to_dict(), path_or_file, **kwargs)
```

`open(p, 'w')` and `io.StringIO` are `io.TextIOBase`; every handle that works today (binary files,
`io.BytesIO`, custom `write(bytes)` objects) is not, and takes the unchanged branch.

### 2.4 Decode errors name the file (R1)

A private module-level helper, after `_as_namespace`, with a one-line docstring:

```python
def _name_the_file(error: ValueError, path: Union[str, os.PathLike]) -> None:
    error.args = (f'{os.fspath(path)}: {error}', )
```

In `from_toml` and `from_json`, path branch only:

```python
with open(path_or_file, mode='rb', **options) as source:      # mode='r' for JSON
    try:
        data = toml.load(source)                               # json.load for JSON
    except toml.TOMLDecodeError as error:                      # json.JSONDecodeError for JSON
        _name_the_file(error, path_or_file)
        raise
return cls(data)
```

The error is the decoder's own object, re-raised: its type, `msg`, `doc`, `pos`, `lineno` and
`colno` are untouched, and only `args` (hence `str()`) changes, to `"{path}: {original}"`. Both
decoders' errors carry exactly one argument on every supported version. The `except` names the
decoder's class, never `ValueError`, so `UnicodeDecodeError` and the integer-digit limit's bare
`ValueError` pass untouched. The handle branches are unchanged (GOAL C2). `Namespace.from_local`
and `Configuration.from_local` reach this through the loaders. YAML is untouched.

### 2.5 Docstrings (R8, § Conventions)

Each of `from_local`, `to_local`, `from_toml`, `from_yaml`, `from_json`, `to_toml`, `to_yaml` and
`to_json` gains a sentence saying a path may be a `str` or an `os.PathLike` (naming `os.PathLike`
literally). At P2, `from_toml` and `from_json` gain a sentence saying a file given by path that
fails to decode raises the decoder's error (naming `TOMLDecodeError` / `JSONDecodeError`) with the
file named in its message. The `docs/api/*.rst` pages are bare `automethod` entries and state no
type, so they need no edit; the annotations render in the signatures. Existing `Example:` blocks
stay.

### 2.6 `Configuration.from_local` (R2, R8)

`src/cmdkit/config.py`: `import os` under `# standard libs`; `**files: Union[str, os.PathLike]`;
a docstring sentence saying each file path may be a `str` or an `os.PathLike`. No code change: each
layer's path goes to `Namespace.from_local` as it is.

### 2.7 Tests

A new class `TestFileLoading` at the end of `tests/test_config.py`; base tests untouched. Its
tests, named in TECH, follow GOAL "How it is shown" 1 to 5. Two shapes the mutant gate needs:
the decode-error test asserts the exact `args` (`(f'{path}: {reference}',)`, the reference being the
decoder's own error on the same text), and the other-errors test asserts that a
`UnicodeDecodeError` from a file has the same `args` and `str()` as decoding the same bytes
directly. The R4 test gives `to_local` one namespace holding a `to_<ext>` key and another holding a
`to_<ext>_eval` key (a `touch` under `tmp_path`), each alone: holding both, `__getattr__` reports
"more than one variant" and a build deciding support on the instance would pass. Subclasses for R3
and R4 are defined inside the test functions.

### Requirement → design map

| R-ID | Design element(s) that satisfy it |
|------|-----------------------------------|
| R1   | § 2.4 `_name_the_file` and the path-branch `except` in `from_toml`, `from_json`; reached by `from_local` and `Configuration.from_local`; § 2.1 for `os.PathLike` paths. P2. |
| R2   | § 2.1 the six `isinstance` tests and the annotations; § 2.2 removes the masking that turned a path failure into `NotImplementedError`; § 2.6. P1. |
| R3   | § 2.2: the method is called outside any handler. P1. |
| R4   | § 2.2: `_NOT_FILE_FORMATS`, the class-level support test, `cls.__name__`, the `to_local` message. P1. |
| R5   | § 2.3 `from_toml` handle branch. P1. |
| R6   | § 2.3 `to_toml` handle branch. P1. |
| R7   | Every line not named above unchanged; § 2.7 adds tests only; the gate's base-tests run, `same` drive corpus and spies (§ 6). P1, P2. |
| R8   | § 2.5, § 2.6, in the same commit as the code (the gate's `static` check 4). P1 (paths), P2 (decode errors). |

## 3. Invariant gate (AGENTS.md constitution check)

Walked before research and again against this design. Sections touched: the high-blast-radius list
(`src/cmdkit/namespace.py`, `src/cmdkit/config.py`), § 1 Compatibility, § 2 Configuration core,
§ 4 Footprint, § Conventions. § 3 (command line) is untouched.

- **High-blast-radius paths.** Both files are on the list, so research ran (trigger 2). `config.py`
  changes only in `from_local`'s annotation and docstring and an import; the gate checks it.
- **§ 1 Compatibility.** GOAL calls each item an outright failure and names the tests that touch the
  old behaviour (`test_from_local`, `test_to_local`, which assert only the `NotImplementedError` type,
  still true). The fix is the default, with no opt-in, as § 1 directs. Every working call keeps its
  result: `str` paths, text handles, binary handles into `to_toml`, `**options`, `ignore_if_missing`,
  `ftype`, a subclass's own `from_<ext>`/`to_<ext>`. No `__all__` name changes; `_name_the_file` and
  `_NOT_FILE_FORMATS` are private. The visible changes for working code are R3's (an error inside a
  loader is no longer `NotImplementedError`) and the readings in the table's first row.
- **§ 2 Configuration core.** Loading never runs an `_eval` or reads an `_env` (the drive's spies,
  § 6); the design removes a path where `to_local` did, by reading the namespace's own keys (§ 2.2).
  Layers, the merge, `_` and `which` are untouched.
- **§ 4 Footprint.** No dependency: `io` and `os` are standard; TOML still comes from the extra and
  `tomllib`. No import-time effect beyond a module constant. The code and the gate run on 3.9.
- **§ Conventions.** Docstrings change with the code, in one commit per phase (gate check 4); no spec
  ids in source, tests or docs (check 5); SPDX blocks and import groups kept (`import io` and
  `import os` under `# standard libs`); the helper has a docstring and annotations; single quotes.

### Deviation justifications

Readings the design takes where GOAL's words admit more than one. None changes what an R-ID SHALL
do as this table reads it; the first four are flagged for the PLAN/TECH sign-off, where a different
ruling goes into GOAL as a clarification.

| Deviation | Why needed | Simpler alternative rejected because |
|-----------|-----------|--------------------------------------|
| Reading (R4, R7): `dict`, `env` and `local` are extensions "with no loader or writer", so `from_local('x.env')` and `to_local('x.env')` (and the other two) raise `NotImplementedError`. Today `x.env` silently returns an `Environ` read from `os.environ` with the prefix `'x.env'`, `x.local` recurses until `RecursionError`, `x.dict` raises `ValueError` / `TypeError`. | R4's wording reaches them: none of these methods loads or writes a file. Each outcome today is an outright failure (§ 1), and the dispatch is the code R4 rewrites. | Leaving them leaves R4 unmet for three extensions, and a `.env` configuration file silently loads the process environment. Seeding them for a later cycle would re-open the same four lines. |
| Reading (R4, R7): an `ftype` outside `toml`, `tml`, `yaml`, `yml`, `json` is ignored and the extension decides, as today (`from_local('c.json', ftype='ini')` loads JSON). R4's "(or `ftype`)" is met wherever an `ftype` chooses the format: every such `ftype` has a loader and writer. | Raising on an unknown `ftype` would break calls that work today, such as `ftype='TOML'` or `ftype=''` on a `.toml` file, which § 1 forbids without a human decision; R7 keeps them. | Using any non-empty `ftype` verbatim (so `ftype='ini'` raises, and a subclass's `from_ini` becomes reachable by `ftype`) changes working calls. The frozen drive pins this reading (`same`: `unknown ftype`, `unknown ftype write`). If the sign-off rules the literal reading, the `ftype` test changes in both methods, those two records move to the drive's R4 group, and the gate is re-frozen before the plan commit lands. |
| Reading (R4, R7): a missing file with `ignore_if_missing=True` returns an empty namespace before any dispatch, whatever its extension (`ini` included), as today. `Configuration.from_local` always passes `True`. | R4 is about choosing a loader; with the file absent and absence allowed, there is nothing to load. R7 keeps today's answer. | Raising first for an unsupported extension would make an application that lists an optional `*.ini` path fail when the file is absent, where today it starts. |
| Reading (R6): "a text handle" is an `io.TextIOBase` (`open(p, 'w')`, `io.StringIO`, the two GOAL names). A duck-typed object whose `write` takes only `str`, or `tempfile.SpooledTemporaryFile('w+')`, keeps today's binary path and today's `TypeError`. | It is the one test that sends every handle that works today down the unchanged branch, byte for byte. | Trying `str` and falling back to `bytes` changes what a permissive custom sink receives; sniffing `'b' in f.mode` breaks on `gzip.GzipFile`, whose `mode` is an `int` on 3.9. |
| Complexity: a module constant `_NOT_FILE_FORMATS` and a private helper `_name_the_file`. | The constant is shared by both dispatch methods; the helper by both loaders. | Inlining each twice restates one rule in two places (§ Conventions: point to a rule). |

## 4. Rabbit holes (resolved)

- **Re-raising a decode error with the path, on five Pythons and two TOML libraries** → rewrite the
  decoder's own error's `args` and re-raise it; the alternatives lose attributes or `str()`
  ([`research/01-decode-errors.md`](research/01-decode-errors.md)).
- **What else is a `ValueError`** → `UnicodeDecodeError` and the integer-digit limit; the `except`
  names the decoder's class (research 01). The mutant gate makes the tests prove it (§ 2.7).
- **The dispatch reaches non-loaders, and `to_local` reaches a namespace's own keys** → found by
  research 02; folded into § 2.2 and the first row of § 3
  ([`research/02-dispatch-paths-handles.md`](research/02-dispatch-paths-handles.md)).
- **Binary and text TOML handles** → read-and-decode in, `io.TextIOBase` out (research 02).
- **Equivalent mutants** → the prototype's `*error.args[1:]` gave two (both decoders' errors carry one
  argument); the design writes a one-tuple. No exclusion is needed: the prototype kills every mutant.
- **Adversarial review** → § 7.

## 5. Risks & open questions

- **Pickling** a rewritten `JSONDecodeError` rebuilds it from `msg`, `doc` and `pos`, so the path is
  lost (the attributes survive). R1 does not cover pickling; accepted, not seeded.
- **Pre-existing, kept by R7, not in this cycle:** `from_toml(path, encoding=...)` raises
  `ValueError` because the options go to a binary `open`; a text-mode `to_toml` by path would
  translate newlines on Windows (identical on POSIX). Neither is seeded by this plan; the sign-off
  may ask for a seed.
- **A known flake in the suite.** `tests/test_app.py::test_app_invalid_options` draws option names
  with Hypothesis and fails about 1 in 40 runs per Python (seeded:
  `issues/test-invalid-options-help-prefix.md`). The gate runs the suite four times (the index's
  and the base's tests, on two Pythons), so roughly one gate run in ten goes red there with no
  change under it; one did in the plan's dry runs. This cycle touches nothing under it; a red of that
  test alone takes the build step's known-flake route.
- **The gate trusts the repository for its own freeze**, as the previous cycle's did: the plan commit
  hash and the tree id below go out of band, so the review can check `git rev-parse
  <plan>:spec/namespace-file-loading/verify` and run the gate from that tree.

## 6. Verification strategy

Frozen gate tree: `f10da12a068f7778a78ce699e490e4fa77c79b1e`

The gate is `sh spec/namespace-file-loading/verify/gate.sh MODE [PHASE]`; its header lists the modes.
It reads the index (stage the phase first), never the working copy, and refuses to run when
`verify/` or this file differs from the plan commit, when a commit before the plan commit changes
anything outside `spec/`, `issues/` and `ROADMAP.md`, or when `verify/`'s tree at HEAD is not the
tree recorded above. cmdkit has no throwaway-environment helper; the gate installs each tree into a
fresh isolated environment with the profile's `verify` packages.

- **`static`**: `change_set.py` (files since the plan; `src/` outside the two files byte for byte;
  `config.py` changed only in `from_local`'s annotations and docstring and an added `os` or `typing`
  import; the eight docstrings and `Configuration.from_local`'s name `os.PathLike`, and at P2
  `from_toml`'s and `from_json`'s name their decode error; code and docstrings first change in the same
  commit; no spec ids in added lines; at P2 the deferral ledger) and `tests_kept.py ast` (every base
  test kept by syntax tree, every file under `tests/` but `test_config.py` byte for byte, the module
  gaining only imports, a `sys.version_info` import block, plain new names and `TestFileLoading` with
  plain or parametrized test functions; every added import from an allowlist (no `zlib`, `ast`,
  `inspect`, `hashlib`, ...); no line that names a module's dunders, a `src/` path, `compile`,
  `eval` or `exec`, or patches a cmdkit name by object or by string; the phase's named tests
  present).
- **`suite`**: the profile's `verify` on 3.9 and 3.14 from an export of the index, with `-rA`, then
  `tests_kept.py passed`: every one of the 156 base node IDs and every named test PASSED, nothing
  failed or skipped. Then the base's own `tests/`, unchanged, against the index's `src/` (installed
  editable, and checked to be what `cmdkit` imports) on both Pythons: all 156 pass (warnings
  allowed, nothing else). That is R7's "every test collected at `386a09a` passes unchanged",
  literally.
- **`drive`**: `drive.py` on 3.9 and 3.14, base and index each in a fresh interpreter, with spies on
  `os.getenv` and `subprocess.check_output`. `same` (142 records): every way of loading and writing
  that works today, the options (writers given `encoding='utf-16'`, loaders given an encoding), binary
  handles into the YAML and JSON methods, a bytes-only sink, a sink taking anything and a `str` reader
  for TOML, the errors that stay (YAML, invalid UTF-8, the 3.11+ integer-digit limit, a missing file,
  handle decode errors with `lineno` and `colno`), a subclass's own format, `Configuration.from_local`
  with `str` layers, an unknown `ftype`, `ignore_if_missing` with `ini`, and loads of files holding
  `_env` and `_eval` keys; every exception recorded with its `args` as well as its message; identical
  on both trees, and no spy call. `expect`: one group per R-ID of the
  phase, from GOAL "How it is shown", using `str`, `pathlib.Path` and a bare `os.PathLike` object;
  every group holds on the index and fails on the base (measured on the prototype: R1 88, R2 62,
  R3 4, R4 35, R5 3, R6 2 base failures).
- **`mutants`**: `mutants.py` on 3.14 over the lines the cycle adds to `src/cmdkit/namespace.py`
  (an expression by every line it spans, a compound statement by its first line; function bodies
  and module-level assignments). Operators: negated tests, `and`/`or` swaps and dropped operands,
  swapped comparisons, dropped `not`, statements to `pass`, integers and slice bounds by one,
  `True`/`False`, `any`/`all`, the first two arguments of a private helper swapped, an `isinstance`
  tuple losing each type, a decode-error `except` widened to `ValueError`, `type(x)` inside
  `hasattr`/`getattr` becoming `x`, an f-string losing each field, and a tuple of strings losing each
  element; class-body assignments count as well as module-level ones. Before any mutant, the
  unmutated source and two equivalent controls (a random comment on top, a dead random assignment
  at the end) must pass, so a test that pins the source text fails the gate. Decisions it mutates:
  - the six path tests (each loses `str` or `os.PathLike`, each negated, each dropped);
  - `_NOT_FILE_FORMATS` (each extension dropped);
  - both support tests (each operand, the operator, `in`, `not`, `type(self)`, the f-strings), both
    messages' fields, both calls;
  - the `from_toml` decode (negated, its `bytes` test dropped) and the `to_toml` text-handle branch;
  - at P2, the helper's message fields, both `except` clauses (widened, bodies to `pass`), the
    re-raise and the `return`.
  Each must make `tests/test_config.py` fail. Measured on the prototype: 60 mutants at P1 (50 s),
  77 at P2 (65 s).
- **`P1`**, **`P2`**: `static`, `suite`, `drive`, `mutants` for the phase. Measured on the
  prototype, each phase's gate on its own tree: P1 58 s, P2 72 s; `prepush` green on the P2 tree.
  Each refuses the tree before it: P1 on the plan commit (every static check red), P2 on the P1
  tree (the decode-error docstrings). **`prepush`**: `static P2` and `suite P2`.

## 7. Adversarial design review

One fresh reviewer, one pass (appetite small), against `GOAL.md`, this design, the drafted gates and
the prototype, attacking copies of the prototype in a throwaway worktree of its own. It ran three
attacks; the gate as drafted passed all three. Its findings, and what changed:

1. **HIGH — a build that rewrote `UnicodeDecodeError`'s `args` passed** (its `str()` comes from its
   fields, so the drive saw nothing), against the non-goal that undecodable bytes raise as today.
   Now the drive records every exception's `args` beside its message, `same` holds the integer-digit
   limit's `ValueError` in TOML and JSON files, the mutant operator for decode-error `except`
   clauses no longer matches `UnicodeDecodeError`, and the design's other-errors test compares
   `args` with a direct decode (§ 2.7).
2. **HIGH — a writer that dropped `encoding` passed**: `same` wrote only ASCII with the default
   encoding. Now `same` writes non-ASCII with `encoding='utf-16'` through every writer and
   `to_local`, reads YAML with an encoding, and pins binary handles into the YAML and JSON methods,
   a bytes-only sink, a sink taking anything (the § 3 reading against try-`str`-then-`bytes`) and a
   `str` reader for TOML.
3. **HIGH — hollow tests passed behind a checksum of the source**, which killed every mutant.
   Now `mutants.py` first runs two equivalent controls (a random comment, a dead random assignment)
   that must pass, and `tests_kept.py` allowlists added imports and refuses module dunders, `src/`
   paths, `compile`/`eval`/`exec` and string-target patches. Checked: the attack's test is refused
   by `static`.
4. **MEDIUM — R4's "(or `ftype`)".** Already a § 3 row; the row now names the two drive records
   that pin it and what moves if the sign-off rules the literal reading.
5. **MEDIUM — a warning line would fail a correct build** in the base-tests run. It now accepts
   `N passed, M warning(s)` and nothing else.
6. **LOW — undecided decisions.** `hasattr(type(self), ...)` to `hasattr(self, ...)` was not
   mutated; now it is, and the prototype's survivor showed the R4 test had to give the `to_<ext>`
   and `to_<ext>_eval` keys to separate namespaces (§ 2.7); the drive's R4 group does the same.
   Class-body assignments are now mutated too.
7. **LOW — a `docs/` page could land apart from the code.** `change_set.py` check 4 now covers any
   page the cycle changes under `docs/`.
8. **LOW — a binary TOML handle decoded leniently would pass.** The drive's R5 group now compares
   invalid UTF-8 from `io.BytesIO` with the same bytes by path.
9. **LOW — the drive demands the decoder's exact type** where R1 says "an instance of". Kept: the
   Outcome says "the same error type", and the design re-raises the decoder's own object.

---

*Backing research: [`research/00-digest.md`](research/00-digest.md).*
