"""Checker for review cycle 1, F1: `to_toml` writes to a handle by the type it takes, whatever its class.

    python -I F1-to-toml-handles.py run > OUT.json
        Run inside the profile's environment for one tree (the launcher runs it on the base and on
        the index, on 3.9 and 3.14). It writes one namespace into every kind of handle and records,
        per kind, what the handle ends up holding and every `write` call it saw. Kinds:

        text    handles whose `write` takes `str` only: `open(p, 'w')`, `io.StringIO`, an
                `io.TextIOWrapper` over `io.BytesIO`, `tempfile.NamedTemporaryFile` in 'w' and 'w+',
                `tempfile.SpooledTemporaryFile('w+')` in memory and rolled over to disk,
                `codecs.open(p, 'w')` (UTF-8 and UTF-16, whose `mode` reads binary),
                `codecs.getwriter('utf-8')` over a binary file, `gzip.open(p, 'wt')`, and a
                str-only object of no io class that logs its calls.
        binary  handles whose `write` takes `bytes`: `open(p, 'wb')`, `io.BytesIO`,
                `tempfile.NamedTemporaryFile('w+b')`, `tempfile.SpooledTemporaryFile('w+b')` in
                memory and rolled over, `gzip.open(p, 'wb')`, `codecs.open(p, 'w', 'hex')` (a codecs
                writer that takes bytes), a bytes-only sink and a sink taking anything (both log
                their calls), and `io.BytesIO` with `multiline_strings=True`.
        errors  a document TOML cannot hold (a None below a value already serialized) into a text
                and a binary handle and the two logging sinks; a sink whose `write` takes neither;
                an unknown keyword into a binary handle.
        read    `from_toml` over each text and binary kind that can be read back: the namespace
                written, by the same rule (what `read` returns decides).

    python -I F1-to-toml-handles.py compare BASE.json HEAD.json
        binary: every record is identical on both trees, write calls included (byte for byte, call
        for call). text: on HEAD every kind holds exactly the TOML text and a logged sink saw one
        `write` carrying the whole document (no probe, nothing partial); on the base at least one
        text kind fails (the check bites). errors: on HEAD the unserializable document raises
        tomli_w's own `TypeError` and every handle is left empty. read: every kind loads the
        namespace on HEAD.

Footprint: one Python process per run, under 100 MB; well under a second.
"""

# type annotations
from __future__ import annotations

# standard libs
import io
import os
import sys
import json
import gzip
import codecs
import shutil
import tempfile
import warnings

DATA = {'a': {'x': 1, 'y': 'café'}, 'b': [1, 2], 'c': {'d': {'e': True}}}


class Log:
    """A sink of no io class: keeps every write, and refuses the types it is told to."""

    def __init__(self, takes: tuple) -> None:
        self.takes = takes
        self.calls = []

    def write(self, chunk):
        if not isinstance(chunk, self.takes):
            raise TypeError(f'{type(self).__name__} takes {self.takes!r}, not {type(chunk).__name__}')
        self.calls.append(chunk)
        return len(chunk)


def main_run() -> None:
    warnings.simplefilter('ignore', DeprecationWarning)  # codecs.open, 3.14
    import tomli_w
    from cmdkit.namespace import Namespace
    ns = Namespace(DATA)
    expected = tomli_w.dumps(DATA)
    tmp = os.path.realpath(tempfile.mkdtemp(prefix='nfl-f1-'))

    def p(name: str) -> str:
        return os.path.join(tmp, name)

    def attempt(fn) -> str:
        try:
            return 'ok ' + repr(fn())
        except Exception as exc:
            return f'{type(exc).__name__}: {exc}'

    def file_bytes(path: str) -> bytes:
        with open(path, 'rb') as stream:
            return stream.read()

    out = {'text': {}, 'binary': {}, 'errors': {}, 'read': {}, 'expected': expected,
           'linesep': os.linesep, 'python': sys.version.split()[0]}

    # text kinds: each returns (what the handle holds as text, the raw bytes behind it or None)
    def text_open():
        with open(p('t-open.toml'), 'w', encoding='utf-8') as stream:
            ns.to_toml(stream)
        with open(p('t-open.toml'), encoding='utf-8') as stream:
            return stream.read(), file_bytes(p('t-open.toml'))

    def text_stringio():
        stream = io.StringIO()
        ns.to_toml(stream)
        return stream.getvalue(), None

    def text_wrapper():
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding='utf-8', newline='')
        ns.to_toml(stream)
        stream.flush()
        return raw.getvalue().decode('utf-8'), raw.getvalue()

    def text_named(mode: str):
        def fn():
            with tempfile.NamedTemporaryFile(mode, encoding='utf-8', suffix='.toml', dir=tmp, delete=False) as stream:
                ns.to_toml(stream)
                name = stream.name
            with open(name, encoding='utf-8') as stream:
                return stream.read(), file_bytes(name)
        return fn

    def text_spooled(max_size: int):
        def fn():
            with tempfile.SpooledTemporaryFile(max_size=max_size, mode='w+', encoding='utf-8', dir=tmp) as stream:
                ns.to_toml(stream)
                rolled = bool(getattr(stream, '_rolled', False))
                stream.seek(0)
                return stream.read(), rolled
        return fn

    def text_codecs_open(encoding: str):
        def fn():
            name = p(f't-codecs-{encoding}.toml')
            stream = codecs.open(name, 'w', encoding)
            mode = stream.mode
            ns.to_toml(stream)
            stream.close()
            data = file_bytes(name)
            return data.decode(encoding), data == expected.encode(encoding), mode
        return fn

    def text_getwriter():
        name = p('t-getwriter.toml')
        with open(name, 'wb') as raw:
            ns.to_toml(codecs.getwriter('utf-8')(raw))
        data = file_bytes(name)
        return data.decode('utf-8'), data

    def text_gzip():
        name = p('t.toml.gz')
        with gzip.open(name, 'wt', encoding='utf-8', newline='') as stream:
            ns.to_toml(stream)
        with gzip.open(name, 'rt', encoding='utf-8', newline='') as stream:
            return stream.read(), None

    def text_log():
        sink = Log((str, ))
        ns.to_toml(sink)
        return ''.join(sink.calls), sink.calls

    for label, fn in [('open w', text_open), ('StringIO', text_stringio), ('TextIOWrapper', text_wrapper),
                      ('NamedTemporaryFile w', text_named('w')), ('NamedTemporaryFile w+', text_named('w+')),
                      ('SpooledTemporaryFile w+', text_spooled(0)),
                      ('SpooledTemporaryFile w+ rolled', text_spooled(8)),
                      ('codecs.open utf-8', text_codecs_open('utf-8')),
                      ('codecs.open utf-16', text_codecs_open('utf-16')),
                      ('codecs.getwriter', text_getwriter), ('gzip wt', text_gzip), ('str-only sink', text_log)]:
        try:
            out['text'][label] = ['ok'] + [repr(v) for v in fn()]
        except Exception as exc:
            out['text'][label] = [f'{type(exc).__name__}: {exc}']

    # binary kinds: the bytes held and, for the logging sinks, every call
    def bin_open():
        with open(p('b-open.toml'), 'wb') as stream:
            ns.to_toml(stream)
        return file_bytes(p('b-open.toml'))

    def bin_bytesio(multiline: bool):
        def fn():
            stream = io.BytesIO()
            if multiline:
                Namespace({'s': 'one\ntwo', **DATA}).to_toml(stream, multiline_strings=True)
            else:
                ns.to_toml(stream)
            return stream.getvalue()
        return fn

    def bin_named():
        with tempfile.NamedTemporaryFile('w+b', dir=tmp) as stream:
            ns.to_toml(stream)
            stream.seek(0)
            return stream.read()

    def bin_spooled(max_size: int):
        def fn():
            with tempfile.SpooledTemporaryFile(max_size=max_size, mode='w+b', dir=tmp) as stream:
                ns.to_toml(stream)
                stream.seek(0)
                return stream.read(), bool(getattr(stream, '_rolled', False))
        return fn

    def bin_gzip():
        name = p('b.toml.gz')
        with gzip.open(name, 'wb') as stream:
            ns.to_toml(stream)
        with gzip.open(name, 'rb') as stream:
            return stream.read()

    def bin_hex():
        name = p('b-hex.txt')
        stream = codecs.open(name, 'w', 'hex')
        ns.to_toml(stream)
        stream.close()
        return file_bytes(name)

    def bin_log(takes):
        def fn():
            sink = Log(takes)
            ns.to_toml(sink)
            return sink.calls
        return fn

    for label, fn in [('open wb', bin_open), ('BytesIO', bin_bytesio(False)),
                      ('BytesIO multiline', bin_bytesio(True)),
                      ('NamedTemporaryFile w+b', bin_named), ('SpooledTemporaryFile w+b', bin_spooled(0)),
                      ('SpooledTemporaryFile w+b rolled', bin_spooled(8)), ('gzip wb', bin_gzip),
                      ('codecs.open hex', bin_hex), ('bytes-only sink', bin_log((bytes, ))),
                      ('any sink', bin_log((str, bytes)))]:
        out['binary'][label] = attempt(fn)

    # errors
    bad = Namespace({'a': 1, 'b': {'c': None}})
    try:
        tomli_w.dumps(bad.to_dict())
    except TypeError as exc:
        out['errors']['reference'] = f'TypeError: {exc}'

    def failing(make, held):
        def fn():
            handle = make()
            try:
                bad.to_toml(handle)
            except Exception as exc:
                return f'{type(exc).__name__}: {exc}', held(handle)
            return 'nothing raised', held(handle)
        return fn

    for label, make, held in [('StringIO', io.StringIO, lambda h: h.getvalue()),
                              ('BytesIO', io.BytesIO, lambda h: h.getvalue()),
                              ('str-only sink', lambda: Log((str, )), lambda h: h.calls),
                              ('bytes-only sink', lambda: Log((bytes, )), lambda h: h.calls)]:
        out['errors'][label] = repr(failing(make, held)())
    out['errors']['takes neither'] = attempt(lambda: ns.to_toml(Log((int, ))))
    out['errors']['unknown keyword'] = attempt(lambda: ns.to_toml(io.BytesIO(), nonsense=1))

    # read: the same rule, what `read` returns decides
    def read_back(kind: str):
        name = p(f'r-{kind}.toml')
        if kind == 'text':
            ns.to_toml(name)
        else:
            with open(name, 'wb') as stream:
                ns.to_toml(stream)
        return name

    def load(make):
        def fn():
            with make() as stream:
                return Namespace.from_toml(stream) == ns
        return fn

    text_file, binary_file = read_back('text'), read_back('binary')

    def spooled_with(mode: str, max_size: int):
        stream = tempfile.SpooledTemporaryFile(max_size=max_size, mode=mode, dir=tmp, **(
            {'encoding': 'utf-8'} if 'b' not in mode else {}))
        ns.to_toml(stream)
        stream.seek(0)
        return stream

    def named_with(mode: str):
        stream = tempfile.NamedTemporaryFile(mode, dir=tmp, **({'encoding': 'utf-8'} if 'b' not in mode else {}))
        ns.to_toml(stream)
        stream.seek(0)
        return stream

    for label, make in [('open r', lambda: open(text_file, encoding='utf-8')), ('open rb', lambda: open(binary_file, 'rb')),
                        ('codecs.open r', lambda: codecs.open(text_file, 'r', 'utf-8')),
                        ('gzip rt', lambda: gzip.open(p('t.toml.gz'), 'rt', encoding='utf-8')),
                        ('gzip rb', lambda: gzip.open(p('b.toml.gz'), 'rb')),
                        ('NamedTemporaryFile w+', lambda: named_with('w+')),
                        ('NamedTemporaryFile w+b', lambda: named_with('w+b')),
                        ('SpooledTemporaryFile w+', lambda: spooled_with('w+', 0)),
                        ('SpooledTemporaryFile w+ rolled', lambda: spooled_with('w+', 8)),
                        ('SpooledTemporaryFile w+b', lambda: spooled_with('w+b', 0)),
                        ('SpooledTemporaryFile w+b rolled', lambda: spooled_with('w+b', 8))]:
        out['read'][label] = attempt(load(make))

    shutil.rmtree(tmp)
    json.dump(out, sys.stdout, indent=1, sort_keys=True)


def main_compare(base_path: str, head_path: str) -> None:
    with open(base_path) as stream:
        base = json.load(stream)
    with open(head_path) as stream:
        head = json.load(stream)
    problems = []
    expected = head['expected']
    if not head['text'] or not head['binary'] or not head['read']:
        problems.append('a corpus is empty')
    for label in sorted(base['binary']):
        if base['binary'][label] != head['binary'].get(label):
            problems.append(f'binary {label}: base {base["binary"][label][:160]} | head '
                            f'{str(head["binary"].get(label))[:160]}')
    for label, record in sorted(head['binary'].items()):
        if not record.startswith('ok '):
            problems.append(f'binary {label} fails: {record[:160]}')
    for label, record in sorted(head['text'].items()):
        if record[0] != 'ok':
            problems.append(f'text {label}: {record[0][:160]}')
            continue
        if record[1] != repr(expected):
            problems.append(f'text {label}: holds {record[1][:120]}, not the TOML text')
        if label == 'str-only sink' and record[2] != repr([expected]):
            problems.append(f'text {label}: write calls {record[2][:160]}, not one call with the document')
        if label in ('codecs.open utf-8', 'codecs.open utf-16') and record[2] != 'True':
            problems.append(f'text {label}: the bytes on disk are not the document in that encoding')
        if label in ('codecs.getwriter', 'TextIOWrapper') and record[2] != repr(expected.encode('utf-8')):
            problems.append(f'text {label}: the bytes are not the UTF-8 document')
        if label == 'open w' and record[2] != repr(expected.replace('\n', head['linesep']).encode('utf-8')):
            problems.append(f'text {label}: the bytes on disk are not the document with this platform\'s newlines')
        if label == 'SpooledTemporaryFile w+ rolled' and record[2] != 'True':
            problems.append(f'text {label}: the file did not roll over, so the case is not covered')
    if all(record[0] == 'ok' and record[1] == repr(expected) for record in base['text'].values()):
        problems.append('text: every kind holds the TOML text on the base (the check does not bite)')
    if 'b' not in head['text'].get('codecs.open utf-8', ['', '', '', "''"])[-1].strip("'"):
        problems.append('text codecs.open utf-8: its mode does not read binary, so the case is not the one F1 names')
    reference = head['errors'].get('reference', '')
    for label, empty in (('StringIO', ''), ('BytesIO', b''), ('str-only sink', []), ('bytes-only sink', [])):
        record = head['errors'].get(label, '')
        if record != repr((reference, empty)):
            problems.append(f'errors {label}: {record[:160]} (want {reference!r} and an empty handle)')
    if not head['errors'].get('takes neither', '').startswith('TypeError: Log takes'):
        problems.append(f'errors takes neither: {head["errors"].get("takes neither")}')
    for label, record in sorted(head['read'].items()):
        if record != 'ok True':
            problems.append(f'read {label}: {record[:160]}')
    for line in problems:
        print('FAIL:', line)
    if problems:
        sys.exit(1)
    bites = sum(1 for record in base['text'].values() if record[0] != 'ok' or record[1] != repr(expected))
    print(f'ok F1 to_toml handles on {head["python"]}: {len(head["text"])} text kinds hold the document, '
          f'{len(head["binary"])} binary kinds identical to the base, {len(head["read"])} read back; '
          f'{bites} text kinds fail on the base; unknown keyword: {head["errors"]["unknown keyword"]}')


def main() -> None:
    args = sys.argv[1:]
    if args == ['run']:
        main_run()
    elif len(args) == 3 and args[0] == 'compare':
        main_compare(args[1], args[2])
    else:
        print('usage: F1-to-toml-handles.py run | compare BASE.json HEAD.json')
        sys.exit(2)


if __name__ == '__main__':
    main()
