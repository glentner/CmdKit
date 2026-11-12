# Research 02: dispatch, paths, handles (R2–R8)

Probed at HEAD `ea704ac` (src/tests/docs identical to `386a09a`) on CPython 3.9.25 (tomli 2.5.0)
and 3.14.6 (tomllib), tomli_w 1.2.0. Results identical on both except traceback wording.

**Verdict.** Every R2–R6 failure has a one-line cause, and the fixes are small and local to
`namespace.py`. `from_local`/`to_local` need no path work: `splitext` and `exists` already take a
`Path`, and they fail only because the loader's `AttributeError` is masked. The design has to make
one real choice. The `getattr` dispatch also reaches `from_dict`/`from_env`/`from_local` (and the `to_*` ones),
and `to_local` looks up on the *instance*, so `NSCoreMixin.__getattr__` can run an `_eval` shell command. Five GOAL readings need a
ruling (end of brief).

## 1. Dispatch (R3, R4)

`from_local` 160–164 and `to_local` 209–213 put the call inside the `try`. `from_*`/`to_*` names on
`Namespace` (both Pythons): `from_dict from_env from_json from_local from_tml from_toml from_yaml
from_yml`, `to_dict to_env to_json to_local to_tml to_toml to_yaml to_yml`. `dict.fromkeys` has no
underscore and is unreachable (`x.keys` → `NotImplementedError`). The extensions that reach a method that isn't a loader or writer:

| ext | `from_local` (file exists) | `to_local` |
|---|---|---|
| `dict` | `ValueError: dictionary update sequence element #0 …` (`cls('x.dict')`) | `TypeError: to_dict() takes 1 positional argument but 2 were given` |
| `env` | **silent wrong value**: `Environ({})`, reads `os.environ` with prefix `'x.env'` | `TypeError: to_env() takes 1 positional …` |
| `local` | `RecursionError` (recurses with `ignore_if_missing` dropped) | `RecursionError` |

Missing file with `ignore_if_missing=True` returns `Namespace({})` for **every** extension, `ini`
included, because the `exists` check (158) runs before dispatch.

**`to_local` dispatches through instance `__getattr__`** (`getattr(self, …)` at 210 → `NSCoreMixin.__getattr__`
80–95): `Namespace({'to_ini_eval': 'touch M'}).to_local('x.ini')` **ran the shell command** (marker
created), then `TypeError: 'str' object is not callable`. `{'to_ini': 5}` gives `TypeError: 'int'
object is not callable`. `{'to_ini_env': …}` reads the variable. So R4 is unmet for any namespace
holding a `to_<ext>` key unless the lookup moves to the class. `from_local` uses `getattr(cls, …)`
and is safe.

R4's literal wording ("no loader or writer") covers `dict`/`env`/`local`, since none of them loads a file.

**`ftype`**: an `ftype` outside `('toml','tml','yaml','yml','json')` (154, 205) is silently ignored and the
extension is used: `from_local('c.json', ftype='ini')` and `ftype='dict'` both load the JSON. So an
`ftype` never reaches a missing method on `Namespace`.

**Extension point**: a subclass adding `from_ini`/`to_ini` works today through `from_local`/`to_local`
(probe: `Ini.from_local('y.ini')` → `Ini({...})`). It is undocumented. No in-repo subclass
uses it (`BuilderNamespace` adds none; `Environ` and `Configuration` are not `Namespace` subclasses), and
HyperShell `src/` defines none (it calls `Namespace.from_toml(filepath)` at `core/config.py:197`).
Invariant 1 argues for keeping it.

**Chaining**: today `NotImplementedError.__context__` is the `AttributeError`; `__cause__` is None. No test
or doc inspects either. `src/` has no `raise … from` anywhere. With only the `getattr` in the `try`,
`from None` just hides the "type object has no attribute" context line, a cosmetic choice. Message
bug: 164 uses `cls.__class__.__name__` (→ `type`); 213 has the stray `."`.

## 2. Paths (R2)

The `str`-only tests are `isinstance(path_or_file, str)` at **170, 183, 193, 218, 227, 236**. That is all of them.
`os.path.splitext` (157, 208) and `os.path.exists` (158) accept `Path`; probe: `splitext(Path('c.toml'))`
→ `('c', '.toml')`, and `from_local(Path('zz.toml'), ignore_if_missing=True)` → `Namespace({})`. Today
`from_toml/yaml/json(Path)` → `AttributeError: 'PosixPath' object has no attribute 'read'`.
`to_*(Path)` → `… no attribute 'write'`. Through `from_local`/`to_local` this surfaces as the
masked `NotImplementedError`. Widening the six tests to `(str, os.PathLike)` (and fixing R3) is
sufficient. `open()` takes `PathLike`.

`Configuration.from_local` (194–214) passes each `filepath` straight to `Namespace.from_local(…,
ignore_if_missing=True)` (211). It needs no code change, only the annotation `**files: str` (195) and the docstring.
`from_context` (237–244) passes `AppContext` paths, which are always `str` (`os.path.join` in
`platform.py` 84–147), so it is unaffected.

Annotations to change: `from_local` `filepath: str` (131), `to_local` `filepath: str` (203),
`path_or_file: Union[str, IO]` (167, 177, 190, 215, 224, 233) → `Union[str, os.PathLike, IO]`;
`Configuration.from_local` `**files: str` → `Union[str, os.PathLike]`. Both modules have
`from __future__ import annotations`, so the annotations are never evaluated (and `os.PathLike[str]`
subscripts fine on 3.9 anyway). **`config.py` does not import `os`**: add it under
`# standard libs`, or `get_type_hints`/autodoc see an undefined name.

## 3. Handles (R5, R6)

`tomllib.load` / `tomli.load` (both versions) is `b = fp.read(); s = b.decode()` (strict UTF-8),
with `AttributeError` → `TypeError("File must be opened in binary mode…") from None`.
`tomli_w.dump` is `for chunk in …: fp.write(chunk.encode())`.

`from_toml` handle branch (187) today: text `open(p)`, `StringIO`, `SpooledTemporaryFile('w+')`,
and a custom `.read()->str` work. `open(p,'rb')`, `BytesIO`, `Spooled('w+b')`, and `.read()->bytes`
fail with `TypeError: Expected str object, not 'bytes'`. **Read, then `.decode()` if bytes**: all 8
load identically, and invalid UTF-8 raises the same `UnicodeDecodeError` as `tomllib.load` (non-goal
holds). Switching to `toml.load(f)` for non-text handles would break the custom `.read()->str`
object, which works today.

`to_toml` handle branch (231) today: `open(p,'wb')`, `BytesIO`, `Spooled('w+b')`, and a custom
`.write(bytes)` work. `open(p,'w')`, `StringIO`, `Spooled('w+')`, and a custom `.write(str)` fail.
`isinstance(h, io.TextIOBase)` is True only for `open(p,'w')` and `StringIO`. `Spooled('w+')` and
custom writers are False and keep today's binary path (and today's failure), so every handle that
works today takes the unchanged branch, byte for byte. Rejected alternatives: try-str-then-bytes
changes what a permissive custom sink receives. Sniffing `'b' in f.mode` breaks on
`gzip.GzipFile`, whose `.mode` is the int `2` on 3.9 (string `'wb'` on 3.14).

Byte equality (both Pythons): path output == `BytesIO` output == `tomli_w.dumps(d).encode()` ==
`StringIO(dumps).getvalue().encode()`. So R6's "same TOML" holds byte for byte. The path branch opens
in text mode, which is identical on POSIX. On Windows it would translate `\n`→`\r\n`, a
pre-existing difference that is out of scope. Side note for R7: `from_toml(path, encoding=…)` →
`ValueError: binary mode doesn't take an encoding argument` (options go to a binary `open`). That is
pre-existing; leave it.

## 4. Docs (R8)

No `.rst` states a path type. `docs/api/namespace.rst` 25–38 and `docs/api/config.rst` 35, 39 are
bare `.. automethod::`. Sphinx `autodoc` uses the default `autodoc_typehints='signature'`
(`docs/conf.py` 38–48), so **the annotations are the rendered type**, and the docstrings are the
prose. The docstrings name no type today: `from_local` 134–137 ("Load from a local file. If
`filepath` does not exist …"), `from_yaml/toml/json` 168/178/191 ("Load a namespace from a X file."),
`to_local` 204 ("Output to local file. If `ftype` not set, format based on file extension."),
`to_yaml/toml/json` 216/225/234 ("Output to X file."), and `Configuration.from_local` 197 ("Create
configuration from a cascade of `files`."). Aliases (243–246) share the docstrings. `docs/index.rst` 84
(`**paths`) and the tutorials state no type. R8 therefore means: change the annotations and add a
sentence to each docstring.

## 5. Tests (R7)

**156 collected** at HEAD on 3.14, all pass. Loader/writer tests: `tests/test_config.py`
`TestNamespace.test_factories` (173: StringIO + `f'{tmp_path}/…'` str paths),
`test_from_local` (187: `FileNotFoundError`, `ignore_if_missing`, `NotImplementedError` on
`.special`, `tml`/`yml`), `test_to_local` (240: round trip, `NotImplementedError`), plus 451–453,
`TestConfiguration.test_from_local` (528), and `test_extend_and_from_local` (858, passes
`str(first)`). They only assert the `NotImplementedError` type, never a message, `__context__`, or
handle failure. `from_toml(StringIO)` is used heavily and must keep working, which read-and-decode
does. Every test writes under `tmp_path`. **No doctest runs**: there is no `--doctest-modules` in
`pyproject.toml` 65–71 or in `.github/workflows/tests.yml` 34. The `Example:` blocks at 120–122 and 147–149 would
write `config.toml` to the cwd if run. Suite run left the tree clean.

## Recommendation for PLAN

- `from_local`: `try: loader = getattr(cls, f'from_{ext}')` / `except AttributeError: raise
  NotImplementedError(f"{cls.__name__} does not currently support '{ext}' files") from None` /
  `return loader(filepath, **options)` outside the `try`. Exclude `ext in ('dict', 'env', 'local')`
  as unsupported, which keeps the subclass `from_<ext>` extension point.
- `to_local`: the same shape, but look up on the class: `writer = getattr(type(self), f'to_{ext}')`,
  then `writer(self, filepath, **options)`. This skips instance `__getattr__` (no `_eval`/`_env`, no
  key shadowing). Message `f'{type(self).__name__} does not currently support "{ext}" files'`.
- Six loaders/writers: `isinstance(path_or_file, (str, os.PathLike))`. Leave the bodies unchanged.
- `from_toml` handle: `data = path_or_file.read()`; `if isinstance(data, bytes): data = data.decode()`;
  `return cls(toml.loads(data))`.
- `to_toml` handle: `if isinstance(path_or_file, io.TextIOBase): path_or_file.write(toml.dumps(d,
  **kwargs))` `else: toml.dump(d, path_or_file, **kwargs)` (add `import io`).
- `config.py`: `import os`; `**files: Union[str, os.PathLike]`; add a docstring sentence. Add a docstring
  sentence to each R2 method. No `.rst` edits are needed for R8 unless the PLAN adds prose.

## Questions for the GOAL

1. **R4 reach**: are `dict`/`env`/`local` "an extension with no loader"? Literally yes. Today `x.env`
   silently returns an `Environ` read from `os.environ`, and `x.local` recurses. Excluding them
   changes those outcomes. (Recommend yes. These are outright failures.)
2. **R4 "(or `ftype`)"**: an unknown `ftype` is silently ignored and the extension wins today
   (`ftype='ini'` on `c.json` loads JSON). Raising on it would change R7 behaviour. Read the clause as
   reachable only through the whitelist (keep today's behaviour), or widen it?
3. **R4 vs `ignore_if_missing`**: a missing `x.ini` with `ignore_if_missing=True` returns empty today,
   and `Configuration.from_local` always passes `True`. Keep the existence check first (R7), or raise
   for an unsupported extension even when the file is absent?
4. **`to_local` class lookup**: R4 needs it for namespaces that hold a `to_<ext>` key. It also closes an
   `_eval` execution path that is outside Invariant 2's literal list (writing). Confirm it is in scope
   for this cycle.
5. **R6 "a text handle"**: read as `io.TextIOBase` (`open(p,'w')`, `StringIO`, the two the GOAL
   names). `SpooledTemporaryFile('w+')` and duck-typed str writers keep failing as today.
