"""Gate: drive file loading and writing, against the base and against GOAL's assertions.

    python -I drive.py run PHASE > OUT.json
        Run inside the profile's environment for one tree (the gate runs it once on the base and
        once on the index, each in a fresh interpreter). It imports the decoders and writers, then
        wraps `os.getenv` and `subprocess.check_output` in spies that record every call made while
        a scenario runs (and pass it on), so a load that expanded `_env` or `_eval` shows. Files go
        under a fresh temporary directory, removed at the end; every record replaces its path with
        `<tmp>`. It runs two corpora and prints JSON.

        same    scenarios whose behaviour must not change, recorded as text: every format written
                and read back by `str` path through `to_local`/`from_local` (by extension and by
                `ftype`), the direct loaders and writers and their aliases, text handles in and
                out, a binary handle into `to_toml`, the options each method passes on (`encoding`,
                `indent`, `sort_keys`, `default_flow_style`, `multiline_strings`, and an encoding
                handed to the binary TOML open), `ignore_if_missing` with a missing `str` path for
                every extension (`ini` included), an unknown `ftype` (the extension decides), a
                missing file, a YAML syntax error, invalid UTF-8 in TOML and JSON files, decode
                errors read from text handles (type, message, `lineno`, `colno`), a subclass's own
                `from_ini`/`to_ini` reached through `from_local`/`to_local`, the class of what a
                subclass loads, `Configuration.from_local` with `str` layers (and a missing one),
                files holding `_env` and `_eval` keys loaded every way with the spies silent, an
                unsupported extension's exception type, writers given `encoding='utf-16'` (directly
                and through `to_local`), `from_yaml` given an encoding, binary handles into the
                YAML and JSON loaders and writers, a bytes-only sink, a sink taking anything and a
                `str` reader for TOML, and integers past the 3.11+ digit limit in TOML and JSON
                files. Every exception is recorded with its `args` as well as its message (object addresses
                masked).
        expect  GOAL's assertions, one group per R-ID, each a list of the problems found on this
                tree:
                R1 (P2) `bad.toml` (`[a]\\nx = \\n`) and `bad.json` (`{"a": }`), by `str`, by
                   `pathlib.Path` and by a bare `os.PathLike`, through the direct loader,
                   `Namespace.from_local` (by extension and by `ftype`) and
                   `Configuration.from_local(user=...)`: the decoder's own error type and a
                   `ValueError`; `str()` holds `os.fspath(path)` and the decoder's own message for
                   the same text; `lineno` and `colno` as the decoder's own error has them.
                R2 every format by `pathlib.Path` and by a bare `os.PathLike` through every loader,
                   writer and alias, `from_local`/`to_local` (by extension and by `ftype`),
                   `ignore_if_missing`, and `Configuration.from_local`: the same bytes written and
                   the same contents read as by `str`.
                R3 subclasses whose `from_json` / `to_json` raise `AttributeError('inner')`,
                   `KeyError('k')` or `TypeError('t')`, called by `str` and by `Path`: the same
                   type and message out of `from_local` / `to_local`.
                R4 `x.ini`, `x.dict`, `x.env` and `x.local` (the file present) through `from_local`
                   and `to_local`, on `Namespace`, on a subclass, and on namespaces holding a
                   `to_<ext>`, a `to_<ext>_env` or a `to_<ext>_eval` key (one each): `NotImplementedError` naming the
                   class and the extension, not the word `type`, not ending in a quote or a period,
                   and no spy call.
                R5 `from_toml` from `open(p, 'rb')`, `io.BytesIO`, `open(p)` and `io.StringIO`: the
                   same `Namespace` as from the path; invalid UTF-8 from `io.BytesIO`: the same
                   `UnicodeDecodeError` (message and `args`) as from the path.
                R6 `to_toml` into `io.StringIO` and `open(p, 'w')`: the same TOML as into
                   `io.BytesIO` and to the path.

    python -I drive.py compare PHASE BASE.json HEAD.json
        `same`: every scenario's record is identical on both trees. `expect`: no group of the
        phase (R2 to R6 at P1, and R1 at P2) has a problem on HEAD, and every one of them has at
        least one on the base (the corpus bites).

Footprint: one Python process, under 100 MB; a second or two per run.
"""

# type annotations
from __future__ import annotations

# standard libs
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

CALLS: list = []
STATE = {'on': False}
GROUPS = {'P1': ['R2', 'R3', 'R4', 'R5', 'R6'], 'P2': ['R1', 'R2', 'R3', 'R4', 'R5', 'R6']}
EXTS = ('toml', 'tml', 'yaml', 'yml', 'json')
FORMAT = {'toml': 'toml', 'tml': 'toml', 'yaml': 'yaml', 'yml': 'yaml', 'json': 'json'}
DATA = {'a': {'x': 1, 'y': 'two', 'z': [1, 2, 3]}, 'b': 3.5, 'c': {'d': {'e': True}}}
BAD = {'toml': '[a]\nx = \n', 'json': '{"a": }'}


class Bare:
    """A path that is an os.PathLike and nothing else."""

    def __init__(self, path: str) -> None:
        self._path = path

    def __fspath__(self) -> str:
        return self._path


def main_run(phase: str) -> None:
    import yaml  # noqa: F401  (imported before the spies go in)
    import tomli_w  # noqa: F401
    if sys.version_info >= (3, 11):
        import tomllib as toml
    else:
        import tomli as toml
    real_getenv, real_check_output = os.getenv, subprocess.check_output

    def spy_getenv(name, *args, **kwargs):
        if STATE['on']:
            CALLS.append(('env', str(name)))
        return real_getenv(name, *args, **kwargs)

    def spy_check_output(cmd, *args, **kwargs):
        if STATE['on']:
            CALLS.append(('eval', str(cmd)))
        return real_check_output(cmd, *args, **kwargs)

    os.getenv = spy_getenv
    subprocess.check_output = spy_check_output
    from cmdkit.namespace import Namespace
    from cmdkit.config import Configuration

    tmp = tempfile.mkdtemp(prefix='nfl-drive-')
    tmp = os.path.realpath(tmp)

    def scrub(text: str) -> str:
        return re.sub(r' at 0x[0-9a-fA-F]+', ' at 0x?', text.replace(tmp, '<tmp>'))

    def p(name: str) -> str:
        return os.path.join(tmp, name)

    def raw(path: str) -> str:
        with open(path, 'rb') as stream:
            return stream.read().decode('utf-8', errors='replace')

    def write(path: str, text: str, mode: str = 'w', **kw) -> str:
        with open(path, mode, **kw) as stream:
            stream.write(text)
        return path

    def attempt(fn) -> str:
        STATE['on'] = True
        try:
            out = 'ok ' + repr(fn())
        except Exception as exc:
            out = f'{type(exc).__name__}: {exc} args={exc.args!r}'
            for attr in ('lineno', 'colno'):
                if hasattr(exc, attr):
                    out += f' [{attr}={getattr(exc, attr)}]'
        finally:
            STATE['on'] = False
        return scrub(out)

    def caught(fn):
        STATE['on'] = True
        try:
            fn()
        except Exception as exc:
            return exc
        finally:
            STATE['on'] = False
        return None

    same: dict = {}
    calls_before = len(CALLS)

    # every format by str path, through to_local / from_local and the direct methods
    ns = Namespace(DATA)
    for ext in EXTS:
        same[f'to_local {ext}'] = attempt(lambda: ns.to_local(p(f's.{ext}')))
        same[f'bytes to_local {ext}'] = raw(p(f's.{ext}'))
        same[f'to_local ftype {ext}'] = attempt(lambda: ns.to_local(p(f's-{ext}.conf'), ftype=ext))
        same[f'bytes to_local ftype {ext}'] = raw(p(f's-{ext}.conf'))
        same[f'from_local {ext}'] = attempt(lambda: Namespace.from_local(p(f's.{ext}')))
        same[f'from_local ftype {ext}'] = attempt(lambda: Namespace.from_local(p(f's-{ext}.conf'), ftype=ext))
        same[f'to_{ext}'] = attempt(lambda: getattr(ns, f'to_{ext}')(p(f'd.{ext}')))
        same[f'bytes to_{ext}'] = raw(p(f'd.{ext}'))
        same[f'from_{ext}'] = attempt(lambda: getattr(Namespace, f'from_{ext}')(p(f'd.{ext}')))
        same[f'ignore missing {ext}'] = attempt(lambda: Namespace.from_local(p(f'missing.{ext}'), ignore_if_missing=True))
        same[f'ignore missing ftype {ext}'] = attempt(
            lambda: Namespace.from_local(p('missing.conf'), ftype=ext, ignore_if_missing=True))
    same['ignore missing ini'] = attempt(lambda: Namespace.from_local(p('missing.ini'), ignore_if_missing=True))
    same['unknown ftype'] = attempt(lambda: Namespace.from_local(p('s.json'), ftype='ini'))
    same['unknown ftype write'] = attempt(lambda: ns.to_local(p('u.json'), ftype='ini'))
    same['bytes unknown ftype write'] = raw(p('u.json'))
    same['missing file'] = attempt(lambda: Namespace.from_local(p('missing.toml')))
    same['missing file json'] = attempt(lambda: Namespace.from_json(p('missing.json')))

    # text handles in, text handles out, a binary handle into to_toml
    text = {ext: raw(p(f's.{ext}')) for ext in ('toml', 'yaml', 'json')}
    same['from_toml StringIO'] = attempt(lambda: Namespace.from_toml(io.StringIO(text['toml'])))
    same['from_yaml StringIO'] = attempt(lambda: Namespace.from_yaml(io.StringIO(text['yaml'])))
    same['from_json StringIO'] = attempt(lambda: Namespace.from_json(io.StringIO(text['json'])))

    def from_open(name: str, path: str):
        with open(path) as stream:
            return getattr(Namespace, name)(stream)
    for ext in ('toml', 'yaml', 'json'):
        same[f'from_{ext} open text'] = attempt(lambda: from_open(f'from_{ext}', p(f's.{ext}')))

    def to_handle(name: str, handle, obj=None, **kw):
        getattr(ns if obj is None else obj, name)(handle, **kw)
        return handle.getvalue()
    same['to_yaml StringIO'] = attempt(lambda: to_handle('to_yaml', io.StringIO()))
    same['to_json StringIO'] = attempt(lambda: to_handle('to_json', io.StringIO()))
    same['to_toml BytesIO'] = attempt(lambda: to_handle('to_toml', io.BytesIO()))

    # options passed on
    latin = write(p('latin.json'), '{"name": "café"}', encoding='latin-1')
    same['from_json encoding'] = attempt(lambda: Namespace.from_json(latin, encoding='latin-1'))
    same['from_local encoding'] = attempt(lambda: Namespace.from_local(latin, encoding='latin-1'))
    same['from_json no encoding'] = attempt(lambda: Namespace.from_json(latin, encoding='utf-8'))
    same['from_toml encoding'] = attempt(lambda: Namespace.from_toml(p('s.toml'), encoding='utf-8'))
    same['to_json indent'] = attempt(lambda: ns.to_json(p('o1.json'), indent=2, sort_keys=True))
    same['bytes to_json indent'] = raw(p('o1.json'))
    same['to_local json kwargs'] = attempt(lambda: ns.to_local(p('o2.json'), indent=None))
    same['bytes to_local json kwargs'] = raw(p('o2.json'))
    same['to_yaml flow'] = attempt(lambda: ns.to_yaml(p('o3.yaml'), default_flow_style=True))
    same['bytes to_yaml flow'] = raw(p('o3.yaml'))
    multi = Namespace({'s': 'one\ntwo'})
    same['to_toml multiline'] = attempt(lambda: multi.to_toml(p('o4.toml'), multiline_strings=True))
    same['bytes to_toml multiline'] = raw(p('o4.toml'))
    same['to_toml BytesIO multiline'] = attempt(lambda: to_handle('to_toml', io.BytesIO(), obj=multi,
                                                                  multiline_strings=True))
    same['to_json StringIO indent'] = attempt(lambda: to_handle('to_json', io.StringIO(), indent=1))
    same['to_toml None'] = attempt(lambda: Namespace({'a': None}).to_toml(p('none.toml')))
    wide = Namespace({'name': 'caf\u00e9 \u2603'})
    for ext in ('toml', 'yaml', 'json'):
        same[f'to_{ext} utf-16'] = attempt(lambda: getattr(wide, f'to_{ext}')(p(f'w16.{ext}'), encoding='utf-16'))
        same[f'bytes to_{ext} utf-16'] = repr(open(p(f'w16.{ext}'), 'rb').read()) if os.path.exists(p(f'w16.{ext}')) else 'none'
        same[f'to_local {ext} utf-16'] = attempt(lambda: wide.to_local(p(f'l16.{ext}'), encoding='utf-16'))
        same[f'bytes to_local {ext} utf-16'] = repr(open(p(f'l16.{ext}'), 'rb').read()) if os.path.exists(p(f'l16.{ext}')) else 'none'
    latin_yaml = write(p('latin.yaml'), 'name: caf\u00e9\n', encoding='latin-1')
    same['from_yaml encoding'] = attempt(lambda: Namespace.from_yaml(latin_yaml, encoding='latin-1'))
    same['from_local yaml encoding'] = attempt(lambda: Namespace.from_local(latin_yaml, encoding='latin-1'))

    def from_binary(name: str, path: str):
        with open(path, 'rb') as stream:
            return getattr(Namespace, name)(stream)
    for ext in ('yaml', 'json'):
        same[f'from_{ext} open binary'] = attempt(lambda: from_binary(f'from_{ext}', p(f's.{ext}')))
        same[f'from_{ext} BytesIO'] = attempt(lambda: getattr(Namespace, f'from_{ext}')(io.BytesIO(text[ext].encode())))
        same[f'to_{ext} BytesIO'] = attempt(lambda: to_handle(f'to_{ext}', io.BytesIO()))

    class BytesSink:
        def __init__(self):
            self.parts = []

        def write(self, chunk):
            if not isinstance(chunk, bytes):
                raise TypeError('bytes only')
            self.parts.append(chunk)

    class AnySink:
        def __init__(self):
            self.parts = []

        def write(self, chunk):
            self.parts.append(chunk)

    def to_sink(sink):
        ns.to_toml(sink)
        return sink.parts
    same['to_toml bytes sink'] = attempt(lambda: to_sink(BytesSink()))
    same['to_toml any sink'] = attempt(lambda: to_sink(AnySink()))
    same['from_toml str reader'] = attempt(lambda: Namespace.from_toml(type('R', (), {'read': lambda self: text['toml']})()))

    # errors that stay as they are
    same['yaml error'] = attempt(lambda: Namespace.from_local(write(p('bad.yaml'), 'a: [1, 2\nb: 3\n')))
    same['yaml error direct'] = attempt(lambda: Namespace.from_yaml(p('bad.yaml')))
    for fmt in ('toml', 'json'):
        bad = write(p(f'utf.{fmt}'), b'a = "\xff"\n' if fmt == 'toml' else b'{"a": "\xff"}', mode='wb')
        same[f'unicode error {fmt}'] = attempt(lambda: Namespace.from_local(bad))
        same[f'unicode error direct {fmt}'] = attempt(lambda: getattr(Namespace, f'from_{fmt}')(bad))
    for fmt, body in (('toml', 'a = ' + '9' * 5000 + '\n'), ('json', '{"a": ' + '9' * 5000 + '}')):
        huge = write(p(f'huge.{fmt}'), body)
        same[f'int limit {fmt}'] = attempt(lambda: len(str(Namespace.from_local(huge)['a'])))
        same[f'int limit direct {fmt}'] = attempt(lambda: len(str(getattr(Namespace, f'from_{fmt}')(huge)['a'])))
    same['toml error StringIO'] = attempt(lambda: Namespace.from_toml(io.StringIO(BAD['toml'])))
    same['json error StringIO'] = attempt(lambda: Namespace.from_json(io.StringIO(BAD['json'])))
    write(p('bad-h.toml'), BAD['toml'])
    write(p('bad-h.json'), BAD['json'])
    same['toml error open text'] = attempt(lambda: from_open('from_toml', p('bad-h.toml')))
    same['json error open text'] = attempt(lambda: from_open('from_json', p('bad-h.json')))
    same['unsupported type'] = attempt(lambda: type(caught(lambda: Namespace.from_local(p('s.toml') + '.ini'))).__name__)
    same['unsupported to type'] = attempt(lambda: type(caught(lambda: ns.to_local(p('x.special')))).__name__)

    # subclasses: their own formats, and what they load
    class Ini(Namespace):
        @classmethod
        def from_ini(cls, path, **options):
            return cls({'ini': os.path.basename(os.fspath(path)), 'options': options})

        def to_ini(self, path, **options):
            write(os.fspath(path), repr(sorted(options.items())))

    write(p('y.ini'), '[x]\n')
    same['subclass from_ini'] = attempt(lambda: Ini.from_local(p('y.ini'), flag=1))
    same['subclass from_ini type'] = attempt(lambda: type(Ini.from_local(p('y.ini'))).__name__)
    same['subclass to_ini'] = attempt(lambda: Ini(DATA).to_local(p('z.ini'), flag=2))
    same['bytes subclass to_ini'] = raw(p('z.ini'))
    same['subclass from_toml type'] = attempt(lambda: type(Ini.from_local(p('s.toml'))).__name__)
    same['subclass from_json type'] = attempt(lambda: type(Ini.from_json(p('s.json'))).__name__)

    # Configuration.from_local with str layers
    def cfg_record(**files):
        cfg = Configuration.from_local(**files)
        return (repr(cfg), cfg.to_dict() if hasattr(cfg, 'to_dict') else dict(cfg),
                [cfg.which('a', 'x'), cfg.which('b')])
    same['configuration str'] = attempt(lambda: cfg_record(system=p('s.toml'), user=p('s.yaml'), local=p('s.json'),
                                                           missing=p('nope.toml')))

    # loading never expands _env or _eval
    lazy = {'k_env': 'NFL_DRIVE_VAR', 'k_eval': 'echo hi', 'sec': {'v_env': 'HOME', 'w_eval': 'false'}}
    Namespace(lazy).to_local(p('lazy.toml'))
    Namespace(lazy).to_local(p('lazy.yaml'))
    Namespace(lazy).to_local(p('lazy.json'))
    before = len(CALLS)
    for ext in ('toml', 'yaml', 'json'):
        same[f'lazy {ext}'] = attempt(lambda: dict(Namespace.from_local(p(f'lazy.{ext}'))))
        same[f'lazy cfg {ext}'] = attempt(lambda: dict(Configuration.from_local(user=p(f'lazy.{ext}'))))
        same[f'lazy write {ext}'] = attempt(lambda: Namespace(lazy).to_local(p(f'lazy2.{ext}')))
    same['lazy spy calls'] = repr(CALLS[before:])
    same['all spy calls'] = repr(CALLS[calls_before:])

    expect = {group: [] for group in GROUPS['P2']}

    # R1
    def reference(fmt: str):
        try:
            (toml.loads if fmt == 'toml' else json.loads)(BAD[fmt])
        except ValueError as exc:
            return exc
        raise AssertionError('the bad text decoded')

    for fmt in ('toml', 'json'):
        ref = reference(fmt)
        path = write(p(f'bad.{fmt}'), BAD[fmt])
        write(p(f'bad-{fmt}.conf'), BAD[fmt])
        for kind, wrap in (('str', str), ('Path', pathlib.Path), ('PathLike', Bare)):
            calls = {
                'direct': lambda: getattr(Namespace, f'from_{fmt}')(wrap(path)),
                'from_local': lambda: Namespace.from_local(wrap(path)),
                'from_local ftype': lambda: Namespace.from_local(wrap(p(f'bad-{fmt}.conf')), ftype=fmt),
                'Configuration': lambda: Configuration.from_local(user=wrap(path)),
            }
            for entry, fn in calls.items():
                where = f'{fmt} {kind} {entry}'
                name = os.fspath(wrap(p(f'bad-{fmt}.conf') if entry == 'from_local ftype' else path))
                exc = caught(fn)
                if exc is None:
                    expect['R1'].append(f'{where}: nothing raised')
                    continue
                if type(exc) is not type(ref) or not isinstance(exc, ValueError):
                    expect['R1'].append(f'{where}: {type(exc).__name__}, not {type(ref).__name__}')
                if name not in str(exc):
                    expect['R1'].append(f'{where}: the message does not hold the path: {scrub(str(exc))}')
                if str(ref) not in str(exc):
                    expect['R1'].append(f'{where}: the message does not hold {str(ref)!r}: {scrub(str(exc))}')
                for attr in ('lineno', 'colno'):
                    if hasattr(ref, attr) and getattr(exc, attr, None) != getattr(ref, attr):
                        expect['R1'].append(f'{where}: {attr} {getattr(exc, attr, None)} != {getattr(ref, attr)}')

    # R2
    for ext in EXTS:
        for kind, wrap in (('Path', pathlib.Path), ('PathLike', Bare)):
            where = f'{ext} {kind}'
            checks = [
                ('to_local', lambda: ns.to_local(wrap(p(f'{kind}.{ext}'))), p(f'{kind}.{ext}'), p(f's.{ext}')),
                ('to_local ftype', lambda: ns.to_local(wrap(p(f'{kind}-{ext}.conf')), ftype=ext),
                 p(f'{kind}-{ext}.conf'), p(f's-{ext}.conf')),
                (f'to_{ext}', lambda: getattr(ns, f'to_{ext}')(wrap(p(f'{kind}-d.{ext}'))),
                 p(f'{kind}-d.{ext}'), p(f'd.{ext}')),
            ]
            for label, fn, out, ref_path in checks:
                got = attempt(fn)
                if got != 'ok None':
                    expect['R2'].append(f'{where} {label}: {got}')
                elif not os.path.exists(out) or raw(out) != raw(ref_path):
                    expect['R2'].append(f'{where} {label}: the bytes differ from the str path\'s')
            reads = [
                ('from_local', lambda: Namespace.from_local(wrap(p(f's.{ext}'))), same[f'from_local {ext}']),
                ('from_local ftype', lambda: Namespace.from_local(wrap(p(f's-{ext}.conf')), ftype=ext),
                 same[f'from_local ftype {ext}']),
                (f'from_{ext}', lambda: getattr(Namespace, f'from_{ext}')(wrap(p(f'd.{ext}'))), same[f'from_{ext}']),
                ('ignore missing', lambda: Namespace.from_local(wrap(p(f'missing.{ext}')), ignore_if_missing=True),
                 same[f'ignore missing {ext}']),
                ('ignore missing ftype',
                 lambda: Namespace.from_local(wrap(p('missing.conf')), ftype=ext, ignore_if_missing=True),
                 same[f'ignore missing ftype {ext}']),
            ]
            for label, fn, want in reads:
                got = attempt(fn)
                if got != want or not got.startswith('ok '):
                    expect['R2'].append(f'{where} {label}: {got} != {want}')
    for kind, wrap in (('Path', pathlib.Path), ('PathLike', Bare)):
        got = attempt(lambda: cfg_record(system=wrap(p('s.toml')), user=wrap(p('s.yaml')), local=wrap(p('s.json')),
                                         missing=wrap(p('nope.toml'))))
        if got != same['configuration str']:
            expect['R2'].append(f'Configuration {kind}: {got}')

    # R3
    for err in (AttributeError('inner'), KeyError('k'), TypeError('t')):
        class Loader(Namespace):
            @classmethod
            def from_json(cls, path, **options):
                raise err

        class Writer(Namespace):
            def to_json(self, path, **options):
                raise err

        for kind, wrap in (('str', str), ('Path', pathlib.Path)):
            for label, fn in (('from_local', lambda: Loader.from_local(wrap(p('s.json')))),
                              ('to_local', lambda: Writer(DATA).to_local(wrap(p('w.json'))))):
                exc = caught(fn)
                if type(exc) is not type(err) or str(exc) != str(err):
                    expect['R3'].append(f'{label} {kind} {type(err).__name__}: got {type(exc).__name__}: {exc}')

    # R4
    class Sub(Namespace):
        pass
    for ext in ('ini', 'dict', 'env', 'local'):
        target = write(p(f'x.{ext}'), '[x]\n')
        cases = [
            ('Namespace', 'from_local', lambda: Namespace.from_local(target)),
            ('Sub', 'from_local', lambda: Sub.from_local(target)),
            ('Namespace', 'from_local Path', lambda: Namespace.from_local(pathlib.Path(target))),
            ('Namespace', 'to_local', lambda: Namespace(DATA).to_local(p(f'out.{ext}'))),
            ('Sub', 'to_local', lambda: Sub(DATA).to_local(p(f'out.{ext}'))),
        ] + [('Namespace', f'to_local holding {key}',
              lambda key=key, value=value: Namespace({key.format(ext): value}).to_local(p(f'out2.{ext}')))
             for key, value in (('to_{}', 5), ('to_{}_env', 'NFL_DRIVE_VAR'), ('to_{}_eval', 'echo hi'))]
        for cls_name, label, fn in cases:
            before = len(CALLS)
            exc = caught(fn)
            where = f'{ext} {cls_name} {label}'
            msg = str(exc)
            if type(exc) is not NotImplementedError:
                expect['R4'].append(f'{where}: {type(exc).__name__}: {scrub(msg)[:120]}')
                continue
            if cls_name not in msg or ext not in msg:
                expect['R4'].append(f'{where}: the message does not name {cls_name} and {ext}: {msg}')
            if re.search(r'\btype\b', msg) or msg.rstrip()[-1:] in ('"', "'", '.'):
                expect['R4'].append(f'{where}: the message names type or ends in a quote or period: {msg}')
            if len(CALLS) != before:
                expect['R4'].append(f'{where}: a spy was called: {CALLS[before:]}')
            if os.path.exists(p(f'out.{ext}')) or os.path.exists(p(f'out2.{ext}')):
                expect['R4'].append(f'{where}: a file was written')

    # R5
    want = same['from_local toml']
    toml_path = p('s.toml')

    def from_handle(mode: str):
        with open(toml_path, mode) as stream:
            return Namespace.from_toml(stream)
    bad_utf = write(p('bad-utf.toml'), b'a = "\xff"\n', mode='wb')
    by_path = attempt(lambda: Namespace.from_toml(bad_utf))
    by_handle = attempt(lambda: Namespace.from_toml(io.BytesIO(b'a = "\xff"\n')))
    if by_handle != by_path or not by_path.startswith('UnicodeDecodeError'):
        expect['R5'].append(f'from_toml BytesIO invalid UTF-8: {by_handle} != {by_path}')
    for label, fn in (('open rb', lambda: from_handle('rb')),
                      ('BytesIO', lambda: Namespace.from_toml(io.BytesIO(raw(toml_path).encode()))),
                      ('open r', lambda: from_handle('r')),
                      ('StringIO', lambda: Namespace.from_toml(io.StringIO(raw(toml_path))))):
        got = attempt(fn)
        if got != want:
            expect['R5'].append(f'from_toml {label}: {got} != {want}')

    # R6
    toml_bytes = raw(p('d.toml'))

    def to_text_open():
        with open(p('t.toml'), 'w') as stream:
            ns.to_toml(stream)
        return raw(p('t.toml'))
    for label, fn in (('StringIO', lambda: to_handle('to_toml', io.StringIO())),
                      ('open w', to_text_open),
                      ('BytesIO', lambda: to_handle('to_toml', io.BytesIO()).decode())):
        got = attempt(fn)
        if got != 'ok ' + repr(toml_bytes):
            expect['R6'].append(f'to_toml {label}: {got[:120]}')

    shutil.rmtree(tmp)
    json.dump({'phase': phase, 'python': sys.version.split()[0], 'same': same, 'expect': expect},
              sys.stdout, indent=1, sort_keys=True)


def main_compare(phase: str, base_path: str, head_path: str) -> None:
    with open(base_path) as stream:
        base = json.load(stream)
    with open(head_path) as stream:
        head = json.load(stream)
    problems = []
    if sorted(base['same']) != sorted(head['same']):
        problems.append('the same corpus has different scenarios on the two trees')
    for key in sorted(base['same']):
        if base['same'][key] != head['same'].get(key):
            problems.append(f'same: {key}:\n      base {base["same"][key][:200]}\n      head '
                            f'{str(head["same"].get(key))[:200]}')
    if head['same'].get('lazy spy calls') != '[]' or head['same'].get('all spy calls') != '[]':
        problems.append('a spy was called while loading or writing')
    for group in GROUPS[phase]:
        for line in head['expect'][group]:
            problems.append(f'expect {group} on HEAD: {line}')
        if not base['expect'][group]:
            problems.append(f'expect {group}: nothing fails on the base (the corpus does not bite)')
    for line in problems:
        print('FAIL:', line)
    if problems:
        sys.exit(1)
    counts = ', '.join(f'{g} {len(base["expect"][g])}' for g in GROUPS[phase])
    print(f'ok drive {phase} on {head["python"]}: {len(head["same"])} same records; '
          f'every expect group holds on HEAD and bites on the base ({counts})')


def main() -> None:
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == 'run' and args[1] in GROUPS:
        main_run(args[1])
    elif len(args) == 4 and args[0] == 'compare' and args[1] in GROUPS:
        main_compare(args[1], args[2], args[3])
    else:
        print('usage: drive.py run P1|P2 | compare P1|P2 BASE.json HEAD.json')
        sys.exit(2)


if __name__ == '__main__':
    main()
