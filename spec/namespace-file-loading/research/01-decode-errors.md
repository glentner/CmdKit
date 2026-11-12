# Research 01 — Naming the file in TOML/JSON decode errors (R1)

**Verdict.** Use mechanism **A**: inside the path branch of `from_toml` and `from_json`, catch exactly
`toml.TOMLDecodeError` / `json.JSONDecodeError` around the `load` call, rewrite
`exc.args = (f'{os.fspath(path)}: {exc}', *exc.args[1:])`, and bare `raise`. It is the only mechanism
that meets R1 on every Python 3.9–3.14 with one code path: same object and type, every attribute
untouched, no chaining, no DeprecationWarning. B needs per-version construction and rewrites `.msg`;
C (`add_note`) fails R1 outright (`str()` excludes notes) and does not exist before 3.11.
Message shape: `"{path}: {original}"`, e.g. `/x/bad.toml: Invalid value (at line 2, column 5)`.

Probes (2026-11-11): CPython 3.9.25 + tomli 2.5.0 (what uv resolves, and the `uv.lock` pin),
3.11.18, 3.12.13, 3.13.16, 3.14.6 (tomllib); tomli 2.0.1/2.0.2/2.1.0/2.2.1 on 3.9 for attributes.

## Q1 — Mechanisms

**Which decoder errors carry attributes** (`msg`, `doc`, `pos`, `lineno`, `colno`):

| decoder | attributes |
|---|---|
| `json.JSONDecodeError`, all versions | all five |
| tomli ≥ 2.1.0 (project floor is `>=2.1.0`; lock 2.5.0) | all five |
| tomli 2.0.x | none |
| tomllib 3.11, 3.12, 3.13 | none (plain `ValueError` subclass, `args=(str,)`) |
| tomllib 3.14 | all five |

In every case `args == (str(exc),)` and `__str__` comes from `BaseException` (it reads `args[0]`).

**A — mutate `args`, bare `raise`.** On every version: `str(e)` = `"<path>: <original>"`;
`type`, `msg`, `doc`, `pos`, `lineno`, `colno` identical to the original (only `args[0]` changes);
`__cause__` None, `__context__` as before (JSON: the decoder's internal `StopIteration(6)`, suppressed —
pre-existing); traceback keeps the decoder's raise frame and the last line reads
`json.decoder.JSONDecodeError: /…/bad.json: Expecting value: line 1 column 7 (char 6)`. No warning
raised under `-W error::DeprecationWarning`. Pickle: TOML keeps the path (default `__reduce__` replays
`args` and restores `__dict__`); **JSON loses the path** on unpickle (`JSONDecodeError.__reduce__`
rebuilds from `msg, doc, pos`), lineno/colno survive. R1 says nothing about pickling.

**B — new `type(exc)` instance, `raise … from exc`.** Works only with per-version construction:
JSON and tomli ≥ 2.1 / tomllib 3.14 need `type(e)(f'{path}: {e.msg}', e.doc, e.pos)`; tomllib
3.11–3.13 (and tomli 2.0) need `type(e)(f'{path}: {e}')`. The naive one-arg form raises
`TypeError: __init__() missing 2 required positional arguments: 'doc' and 'pos'` for JSON, and for
tomli 2.5 / tomllib 3.14 emits `DeprecationWarning: Free-form arguments for TOMLDecodeError are
deprecated` and drops every attribute (`lineno` absent — violates R1). The correct form rewrites
`.msg` to include the path, adds a chained "direct cause" traceback block, and pickles with the path.

**C — `add_note`.** `str(e)` is unchanged (`'Invalid value (at line 2, column 5)'`, path only in
`__notes__`), so R1's "message contains the path" fails; unavailable on 3.9/3.10. Rejected.

Pre-existing, not ours: pickling *any* tomli ≥ 2.1 / tomllib 3.14 `TOMLDecodeError` (original or A)
emits the free-form DeprecationWarning on `loads`, because default `__reduce__` calls `cls(*args)`.

## Q2 — What to catch

Catch exactly `toml.TOMLDecodeError` (the module chosen by the existing `sys.version_info` import)
and `json.JSONDecodeError`. Probed outcomes (identical on 3.9/tomli, 3.11, 3.14):

| input | raises | rewritten by A? |
|---|---|---|
| TOML/JSON syntax error, bad date `2021-02-30`, NUL byte, dup key, BOM-led file | decoder's error | yes |
| invalid UTF-8 (`b'\xff'`) — TOML (`load` decodes bytes itself) and JSON (text-mode read) | `UnicodeDecodeError` (a `ValueError`, not a decoder error) | no (passes) |
| 5000-digit int / hex, TOML and JSON | bare `ValueError: Exceeds the limit (4300…) for integer string conversion` | no (passes) |
| deep nesting (TOML arrays/inline tables, JSON arrays) | `RecursionError` | no (passes) |
| `x = 1e99999` (TOML), `NaN` (JSON) | loads (`inf`, `nan`) | n/a |

The int-limit `ValueError` is the only non-decoder `ValueError` found for bad input. It is outside
R1: R1 requires "the decoder's own error type", which it is not, and catching `ValueError` to
cover it would also catch `UnicodeDecodeError` against the Non-goals and R7. Leave it; a seed if wanted.

## Q3 — Where the catch sits

`Namespace.from_local` dispatches through `getattr(cls, f'from_{ext}')`, and
`Configuration.from_local` (`config.py:211`) calls `Namespace.from_local(filepath, ignore_if_missing=True)`
per layer, with no `try` of its own. So the catch belongs **inside the path branch of `from_toml` and
`from_json`**, wrapping only the `load(source)` call (keep `cls(...)` outside the `try`); the
`from_tml` alias is the same function object. The handle branch gets no `try`. `from_local`'s
`except AttributeError` never sees a `ValueError`, so R3's fix there does not interact.

Placement confirmed end to end on 3.9 and 3.14 by monkeypatching that shape onto `Namespace` (worktree
source, read-only): `from_toml(str)`, `from_toml(Path)`, `Namespace.from_local(str)`,
`Configuration.from_local(user=str)` — and the same four for JSON — all gave
`str(e) == f"{path}: {original}"`, `isinstance(e, ValueError)`, lineno/colno 2/5 (TOML) and 1/7
(JSON); a `StringIO` handle's message was unchanged; an invalid-UTF-8 JSON path raised an unchanged
`UnicodeDecodeError`. (The `Path` and `from_local(Path)` cases also need R2's
`isinstance(path_or_file, (str, os.PathLike))`.)

## Q4 — Portable test

```python
if sys.version_info >= (3, 11):
    import tomllib as toml_reader
else:
    import tomli as toml_reader          # in the dev group; lock pins 2.5.0
TOMLDecodeError = toml_reader.TOMLDecodeError
```

Per format: write the bad text, compute the reference error from the decoder directly
(`toml_reader.loads(text)` / `json.loads(text)`), then for each entry point
`with pytest.raises(TOMLDecodeError, match=re.escape(os.fspath(path))) as info:` and assert
`isinstance(info.value, ValueError)`, `str(ref) in str(info.value)`, and
`getattr(info.value, a, None) == getattr(ref, a, None)` for `a in ('lineno', 'colno')` — this checks
"unchanged" where the attributes exist and passes vacuously on 3.11–3.13. Optionally pin the
literals when `hasattr(ref, 'lineno')`. Test `str` and `Path` paths both (`Path` depends on R2).

Expected values, from probes:

| input | Python | `str(original)` | lineno, colno |
|---|---|---|---|
| `[a]\nx = \n` | 3.9 + tomli 2.5.0, 3.14 | `Invalid value (at line 2, column 5)` | 2, 5 |
| `[a]\nx = \n` | 3.11–3.13 | same | absent |
| `{"a": }` | all | `Expecting value: line 1 column 7 (char 6)` | 1, 7 |

The verify Pythons (3.9 + tomli 2.5.0 and 3.14) both carry the attributes, so the lineno/colno
assertion is live on both.

## Recommendation for PLAN

1. Add one private helper in `namespace.py`, e.g.
   `def _name_file(exc: ValueError, path) -> None: exc.args = (f'{os.fspath(path)}: {exc}', *exc.args[1:])`.
2. In `from_toml` and `from_json`, path branch only:
   `with open(path, …) as source: try: data = toml.load(source) except toml.TOMLDecodeError as exc: _name_file(exc, path); raise` then `return cls(data)`.
   Catch exactly the decoder error class; never `ValueError`.
3. Message shape `"{os.fspath(path)}: {original}"` — grep-style, keeps the decoder's text verbatim
   and last, and keeps `msg`/`lineno`/`colno` as the decoder set them.
4. Known, accepted: an A-rewritten `JSONDecodeError` loses the path through pickle (attributes kept).
   Document nothing for it; R1 does not cover pickling.
5. Out of scope, pass through unchanged: `UnicodeDecodeError`, int-limit `ValueError`,
   `RecursionError`, `OSError`s from `open`.
