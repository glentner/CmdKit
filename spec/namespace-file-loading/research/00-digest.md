# Research digest — namespace-file-loading

Two briefs, run because the change touches `src/cmdkit/namespace.py` and `src/cmdkit/config.py`
(high-blast-radius paths). Both probed on 3.9 (tomli 2.5.0) and 3.14 (tomllib), and 01 also on
3.11 to 3.13. They do not contradict each other; the decisions below are the plan's.

## Decisions

1. **Decode errors (R1): rewrite the decoder's own error in place.** In the path branch of
   `from_toml` and `from_json`, catch exactly `toml.TOMLDecodeError` / `json.JSONDecodeError`
   around the `load` call, set `error.args = (f'{os.fspath(path)}: {error}',)`, and re-raise it with
   a bare `raise`. The type, `msg`, `doc`, `pos`, `lineno` and `colno` stay as the decoder set them,
   on every Python, with no chaining and no warning. A new instance (`raise type(e)(...) from e`)
   needs a constructor per version and loses attributes on tomli 2.5 and 3.14; `add_note` leaves
   `str()` unchanged and is missing on 3.9. Both decoders' errors carry exactly one argument, so the
   new `args` is a one-tuple (the prototype's `*error.args[1:]` was an equivalent mutant).
   ([01](01-decode-errors.md))
2. **What passes through.** `UnicodeDecodeError` (a `ValueError`), the 3.11+ integer-digit limit's
   bare `ValueError`, `RecursionError` and `OSError` are not the decoder's error type and come
   through untouched. The `except` names the decoder's class, never `ValueError`. ([01](01-decode-errors.md))
3. **Paths (R2).** The six `isinstance(path_or_file, str)` tests are the only places a `str` is
   assumed; they admit `os.PathLike`. `splitext`, `exists` and `open` already take one.
   `Configuration.from_local` and `from_context` need no code change; the annotation does, and
   `config.py` gains `import os` for it. ([02](02-dispatch-paths-handles.md))
4. **Dispatch (R3, R4).** The lookup leaves the `try`: decide support first, then call the method
   outside any handler, so nothing it raises is caught. The extensions `dict`, `env` and `local`
   name methods that are not file loaders or writers (`x.env` silently returns an `Environ` read
   from `os.environ`; `x.local` recurses), so they are unsupported. `to_local` decides support on
   `type(self)`: on the instance, the lookup falls through to `NSCoreMixin.__getattr__`, which reads
   a namespace's own `to_<ext>`, `to_<ext>_env` or `to_<ext>_eval` key (a probe ran the shell
   command). A subclass's own `from_<ext>` / `to_<ext>` keeps working. ([02](02-dispatch-paths-handles.md))
5. **Handles (R5, R6).** `from_toml` reads the handle and decodes `bytes` as UTF-8, as `tomllib.load`
   does; every handle that loads today still does. `to_toml` writes `tomli_w.dumps(...)` to an
   `io.TextIOBase` (`open(p, 'w')`, `io.StringIO`) and keeps `tomli_w.dump` for everything else, so
   every handle that works today takes the unchanged branch. The TOML is byte for byte the same
   either way. ([02](02-dispatch-paths-handles.md))
6. **Docs (R8).** No `.rst` states a path type (all bare `automethod`); the annotations render in the
   signatures, and each docstring gains a sentence. ([02](02-dispatch-paths-handles.md))
7. **Tests (R7).** 156 tests collected at the base; none checks a message, the masking or a handle
   failure, and no doctest runs. ([02](02-dispatch-paths-handles.md))

## Readings the plan chose (PLAN § 3, for the sign-off)

- `dict`, `env`, `local` are extensions with no loader or writer (R4).
- An `ftype` outside the five known ones is ignored and the extension decides, as today (R4, R7).
- A missing file with `ignore_if_missing=True` returns an empty namespace before any dispatch,
  whatever its extension, as today (R4, R7).
- "A text handle" in R6 is an `io.TextIOBase`.
