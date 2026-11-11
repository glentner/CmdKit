"""Gate: a write audit of whole pytest runs, through a Python audit hook (R1, R3, R4).

Standard library only, and Python 3.9 syntax: `run` executes under each of the profile's Pythons.

    python -I write_audit.py run --log LOG --root ROOT --token TOKEN [--barrier DIR --peers N] -- ARGS
        Installs a `sys.addaudithook` hook, then imports pytest and runs `pytest.main(ARGS)` in
        ROOT. Records every path opened for writing, created, renamed, removed, linked or modified
        (`os.utime`, `os.chmod`, `os.chown`, `os.truncate`, extended attributes and flags, file
        descriptors resolved to their paths), every SQLite database opened, every AF_UNIX socket
        bound, every path a test opened for reading, every process spawned or forked, and every
        native library a test loads, each with the code that asked for it. Lists the files under
        ROOT before and after the run. Recording continues until interpreter shutdown: the log is
        written by the first `atexit` handler registered, so it runs after every other one and after
        every non-daemon thread has been joined; the number of threads still alive when
        `pytest.main` returns is logged. Exits with pytest's status. TOKEN only marks the process.
        With --barrier, waits (up to 120 s) until N runs have reached DIR before starting pytest,
        so concurrent runs overlap.

    python -I write_audit.py check LOG --allow DIR [--allow DIR ...] [--expect-names FILE]
        R1. Every recorded write lies under an --allow directory, or is a tool-cache write (C1):
        under ROOT/.pytest_cache (or the `pytest-cache-files-*` directory pytest builds it in),
        ROOT/.hypothesis, or a `__pycache__` directory under ROOT or under an import root, asked
        for by the import system, pytest or Hypothesis, and never by a test or by cmdkit; a write
        pytest's `cache` fixture makes for a test is the test's. Two writes of pytest's own output
        capture are set aside too, and only when pytest's code asks for them: `os.devnull`, and a
        temporary file directly in the system temporary directory that pytest's code also removes
        during the run (with the directory itself, opened to make one). Every spawned process is a
        shell running a plain `echo` (the suite's `_eval` values); a fork is a violation, and so is
        a native library a test's code (or cmdkit) loads through ctypes. No thread outlived `pytest.main`. Nothing under ROOT
        changed except those caches. pytest exited 0. With --expect-names, the base names of the
        files the tests (or cmdkit, called from a test) opened for writing are exactly the lines of
        FILE (the hook saw the tests' own writes, and R5's file names are unchanged).

    python -I write_audit.py cross LOG_A LOG_B
        R4. No file a test of one run wrote (outside the C1 caches) was read or written by a
        test of the other run, and each run's tests wrote something. A test's write is one its own
        code, cmdkit or the standard library asked for (the innermost frame outside the standard
        library, or none), or any other write made while a test frame is on the stack except the
        import system's, Hypothesis's, and pytest's bookkeeping for its numbered directories
        (`pytest-of-*/`, `pytest-current`, `pytest-N/`, their lock files).

    python -I write_audit.py selftest --work DIR
        The hook's own check: a canary suite under DIR writes outside its basetemp by every route
        the hook claims to see, and each one must be reported; its tmp_path writes and an `echo`
        spawn must not be. Two canary runs share fixed files, one through a thread running
        standard-library code, and `cross` must report both.

What the hook can't see: writes made by a spawned process (hence the spawn rule and the listing
of ROOT), by C code that bypasses Python's os and io layers (hence loading a native library from
a test is a violation), by `os.open(..., dir_fd=)` with a relative path (its audit event
carries no dir_fd; the path is resolved against the working directory instead), and by
`os.mkfifo` and `os.mknod`, which raise no audit event (checked on 3.9 and 3.14).

Footprint: one Python process per `run` (two at once in the gate's concurrent mode), under
100 MB each; the canary self-test runs two short pytest processes one after another.
"""

# type annotations
from __future__ import annotations

# standard libs
import argparse
import atexit
import json
import os
import re
import subprocess
import stat
import sys
import sysconfig
import tempfile
import threading
import time

try:  # macOS: resolve a file descriptor to its path
    import fcntl
except ImportError:  # pragma: no cover (Windows)
    fcntl = None

WRITE_BITS = (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
              | getattr(os, 'O_EXCL', 0))

# event: [(path index, dir_fd index or None, kind, follow the last component)]
PATH_EVENTS = {
    'os.mkdir': [(0, 2, 'create', False)],
    'os.rename': [(0, 2, 'rename', False), (1, 3, 'rename', False)],
    'os.remove': [(0, 1, 'remove', False)],
    'os.rmdir': [(0, 1, 'remove', False)],
    'os.symlink': [(1, 2, 'create', False)],
    'os.link': [(0, 2, 'modify', True), (1, 3, 'create', False)],
    'os.truncate': [(0, None, 'write', True)],
    'os.utime': [(0, 3, 'modify', True)],
    'os.chmod': [(0, 2, 'modify', True)],
    'os.chown': [(0, 3, 'modify', True)],
    'os.chflags': [(0, None, 'modify', True)],
    'os.lchflags': [(0, None, 'modify', False)],
    'os.setxattr': [(0, None, 'modify', True)],
    'os.removexattr': [(0, None, 'modify', True)],
    'shutil.rmtree': [(0, 1, 'remove', False)],
    'sqlite3.connect': [(0, None, 'write', True)],
}
# event: index of the argv (or command string) in its arguments; None for a fork
SPAWN_EVENTS = {
    'subprocess.Popen': 1, 'os.system': 0, 'os.posix_spawn': 1, 'os.exec': 1,
    'os.spawn': 2, 'os.startfile': 0, 'pty.spawn': 0, 'os.fork': None, 'os.forkpty': None,
}
INTERESTING = (frozenset(['open', 'socket.bind', 'ctypes.dlopen']) | frozenset(PATH_EVENTS)
               | frozenset(SPAWN_EVENTS))
CACHE_TOPS = ('.pytest_cache', '.hypothesis')
CACHE_WRITERS = frozenset(['import', 'pytest', 'hypothesis'])
ECHO = re.compile(r'^(?:\S*[\\/])?(?:sh|bash|dash|cmd|cmd\.exe)\s+[-/]c\s+"?echo(?: [A-Za-z0-9_.-]+)+"?$',
                  re.IGNORECASE)
WRITE_KINDS = frozenset(['write', 'create', 'rename', 'remove', 'modify'])
TEST_WRITERS = frozenset(['test', 'cmdkit', 'stdlib'])
BOOKKEEPING = re.compile(r'^pytest-of-[^/\\]+(?:[/\\](?:pytest-current|pytest-\d+(?:[/\\]\.lock\S*)?))?$')


def real(p: str, follow: bool = False) -> str:
    """Absolute, normalized, every directory component resolved; the last one too with `follow`."""
    p = os.path.normpath(os.path.abspath(p))
    if follow:
        return os.path.realpath(p)
    head, tail = os.path.split(p)
    return os.path.join(os.path.realpath(head), tail)


def under(p: str, root: str) -> bool:
    return p == root or p.startswith(root.rstrip(os.sep) + os.sep)


# --------------------------------------------------------------------------------------------
# run: the hook


class Recorder:

    def __init__(self, root: str) -> None:
        self.root = real(root)
        self.tests = os.path.join(self.root, 'tests')
        self.src = os.path.join(self.root, 'src')
        stdlib = {sysconfig.get_paths()[k] for k in ('stdlib', 'platstdlib')}
        self.stdlib = [os.path.realpath(p) for p in stdlib]
        self.records: list[dict] = []
        self.on = False
        self.local = threading.local()
        self.kinds: dict[str, str] = {}

    def kind_of(self, filename: str) -> str:
        kind = self.kinds.get(filename)
        if kind is None:
            kind = self.kinds[filename] = self._kind_of(filename)
        return kind

    def _kind_of(self, filename: str) -> str:
        if filename.startswith('<frozen importlib') or filename.startswith('<frozen zipimport'):
            return 'import'
        if filename.startswith('<'):
            return 'stdlib'
        path = os.path.realpath(filename)
        if under(path, self.tests):
            return 'test'
        if under(path, self.src):
            return 'cmdkit'
        parts = path.split(os.sep)
        for marker in ('site-packages', 'dist-packages'):
            if marker in parts:
                i = len(parts) - 1 - parts[::-1].index(marker)
                top = parts[i + 1] if i + 1 < len(parts) else ''
                if top in ('_pytest', 'pytest', 'pluggy') or top.startswith('pytest'):
                    return 'pytest'
                if top == 'hypothesis' or top.startswith('_hypothesis'):
                    return 'hypothesis'
                return 'lib:' + top
        if any(under(path, s) for s in self.stdlib):
            return 'stdlib'
        if under(path, self.root):
            return 'root'
        return 'other:' + path

    def stack(self) -> tuple[str, bool]:
        """The innermost frame that isn't the standard library names the writer."""
        writer, in_test = '', False
        frame = sys._getframe(3)
        while frame is not None:
            kind = self.kind_of(frame.f_code.co_filename)
            if not writer and kind != 'stdlib':
                writer = kind
            if kind == 'test':
                in_test = True
            frame = frame.f_back
        return writer or 'stdlib', in_test

    @staticmethod
    def fd_path(fd: int) -> str:
        if sys.platform.startswith('linux'):
            return os.readlink(f'/proc/self/fd/{fd}')
        if sys.platform == 'darwin' and fcntl is not None:
            raw = fcntl.fcntl(fd, fcntl.F_GETPATH, bytes(1024))
            return os.fsdecode(raw.split(b'\0', 1)[0])
        raise OSError(f'cannot resolve file descriptor {fd} on {sys.platform}')

    def resolve(self, path, dir_fd, follow: bool) -> str:
        try:
            if isinstance(path, int):
                return real(self.fd_path(path), follow=True)
            p = os.fsdecode(os.fspath(path))
            if not os.path.isabs(p):
                base = self.fd_path(dir_fd) if isinstance(dir_fd, int) and dir_fd >= 0 else os.getcwd()
                p = os.path.join(base, p)
            return real(p, follow)
        except Exception as error:  # fail closed: an unresolved path is a violation
            return f'<unresolved {path!r} dir_fd={dir_fd!r}: {error}>'

    def hook(self, event: str, args: tuple) -> None:
        if event not in INTERESTING or not self.on or getattr(self.local, 'busy', False):
            return
        self.local.busy = True
        try:
            self._hook(event, args)
        finally:
            self.local.busy = False

    def add(self, event: str, kind: str, writer: str, in_test: bool, **more) -> None:
        self.records.append(dict(event=event, kind=kind, writer=writer, test=in_test, **more))

    def _hook(self, event: str, args: tuple) -> None:
        if event == 'open':
            path, mode, flags = (tuple(args) + (None, None, None))[:3]
            if isinstance(path, int):
                return  # wrapping a descriptor some earlier event opened
            if isinstance(flags, int):
                write = bool(flags & WRITE_BITS)
            else:
                write = isinstance(mode, str) and any(c in mode for c in 'wax+')
            writer, in_test = self.stack()
            if not write and not in_test:
                return
            self.add(event, 'write' if write else 'read', writer, in_test,
                     path=self.resolve(path, None, True))
        elif event in PATH_EVENTS:
            writer, in_test = self.stack()
            for i, j, kind, follow in PATH_EVENTS[event]:
                if i >= len(args) or args[i] is None:
                    continue
                if event == 'sqlite3.connect' and args[i] in (':memory:', '', b':memory:', b''):
                    continue
                dir_fd = args[j] if j is not None and j < len(args) else None
                self.add(event, kind, writer, in_test, path=self.resolve(args[i], dir_fd, follow))
        elif event == 'socket.bind':
            address = args[1] if len(args) > 1 else None
            if isinstance(address, (str, bytes)) and address and address[:1] not in ('\0', b'\0'):
                writer, in_test = self.stack()
                self.add(event, 'create', writer, in_test, path=self.resolve(address, None, False))
        elif event == 'ctypes.dlopen':
            writer, in_test = self.stack()
            self.add(event, 'native', writer, in_test, argv=repr(args[0] if args else None))
        else:
            writer, in_test = self.stack()
            index = SPAWN_EVENTS[event]
            if index is None:
                argv = f'<{event}>'
            else:
                argv = args[index] if index < len(args) else args
            if isinstance(argv, (list, tuple)):
                argv = [os.fsdecode(a) if isinstance(a, (str, bytes, os.PathLike)) else repr(a) for a in argv]
            else:
                argv = os.fsdecode(argv) if isinstance(argv, (str, bytes, os.PathLike)) else repr(argv)
            self.add(event, 'spawn', writer, in_test, argv=argv)


def listing(root: str) -> dict:
    out = {}
    for top, dirs, files in os.walk(root):
        for name in dirs + files:
            p = os.path.join(top, name)
            try:
                st = os.lstat(p)
            except OSError:
                continue
            # a directory's own size and time move with its entries: only its presence counts
            key = [0, 0, st.st_mode] if stat.S_ISDIR(st.st_mode) else [st.st_size, st.st_mtime_ns, st.st_mode]
            out[os.path.relpath(p, root)] = key
    return out


def barrier(directory: str, token: str, peers: int) -> None:
    os.makedirs(directory, exist_ok=True)
    with open(os.path.join(directory, f'{token}-{os.getpid()}'), 'w') as stamp:
        stamp.write(str(os.getpid()))
    deadline = time.monotonic() + 120
    while len(os.listdir(directory)) < peers:
        if time.monotonic() > deadline:
            sys.exit(f'FAIL: barrier: {len(os.listdir(directory))} of {peers} runs arrived in 120 s')
        time.sleep(0.05)


def run(opts: argparse.Namespace) -> None:
    root = real(opts.root)
    os.chdir(root)
    before = listing(root)
    if opts.barrier:
        barrier(opts.barrier, opts.token, opts.peers)
    rec = Recorder(root)
    state = {'exit': 99, 'threads': -1}
    log = {
        'root': root, 'python': sys.version, 'platform': sys.platform, 'pid': os.getpid(),
        'system_tmp': os.path.realpath(tempfile.gettempdir()),
        'import_roots': sorted({real(p) for p in sys.path if p and os.path.isdir(p)}),
    }

    def finish() -> None:
        rec.on = False  # hooks can't be removed; this stops the recording
        log.update(exit=state['exit'], threads_after_main=state['threads'], records=rec.records,
                   changed=sorted(k for k in set(before) | set(after(root)) if before.get(k) != after(root).get(k)))
        with open(opts.log, 'w') as stream:
            json.dump(log, stream, indent=1)

    cache = {}

    def after(path: str) -> dict:
        if 'listing' not in cache:
            cache['listing'] = listing(path)
        return cache['listing']

    atexit.register(finish)  # first registered, so it runs last
    sys.addaudithook(rec.hook)
    rec.on = True
    import pytest
    state['exit'] = int(pytest.main(list(opts.args)))
    state['threads'] = threading.active_count()
    sys.exit(state['exit'])


# --------------------------------------------------------------------------------------------
# check and cross: the verdicts


def is_cache(path: str, log: dict) -> bool:
    root = log['root']
    if any(under(path, os.path.join(root, top)) for top in CACHE_TOPS):
        return True
    if path == root:  # pytest's cache provider asks for the root with exist_ok
        return True
    rel = os.path.relpath(path, root)
    if not rel.startswith('..') and rel.split(os.sep)[0].startswith('pytest-cache-files-'):
        return True  # pytest builds .pytest_cache in a temporary sibling, then renames it
    if '__pycache__' in path.split(os.sep):
        return any(under(path, r) for r in [root] + log['import_roots'])
    return False


def cache_ok(r: dict, log: dict) -> bool:
    """A C1 cache write the tools made for themselves, not for a test."""
    if not is_cache(r['path'], log) or r['writer'] not in CACHE_WRITERS:
        return False
    if r['writer'] == 'pytest' and r['test'] and under(r['path'], os.path.join(log['root'], '.pytest_cache')):
        return False  # the `cache` fixture writing for a test
    return True


def cache_change(rel: str) -> bool:
    parts = rel.split(os.sep)
    return parts[0] in CACHE_TOPS or parts[0].startswith('pytest-cache-files-') or '__pycache__' in parts


def describe(r: dict) -> str:
    where = r.get('path', r.get('argv'))
    return f"{r['event']} {r['kind']} {where} (by {r['writer']}{', in a test' if r['test'] else ''})"


def capture_temp(r: dict, log: dict, removed: set) -> bool:
    """pytest's own output capture: os.devnull, or an anonymous file in the system temp dir."""
    if r['writer'] != 'pytest':
        return False
    p, tmp = r['path'], log['system_tmp']
    if p == real(os.devnull, follow=True) or p == tmp:
        return True
    return os.path.dirname(p) == tmp and p in removed


def violations(log: dict, allow: list) -> list:
    allow = [real(a, follow=True) for a in allow]
    removed = {r['path'] for r in log['records'] if r['kind'] == 'remove' and r['writer'] == 'pytest'}
    out = []
    for r in log['records']:
        if r['kind'] == 'spawn':
            argv = r['argv'] if isinstance(r['argv'], str) else ' '.join(r['argv'])
            if not ECHO.match(argv):
                out.append('spawn: ' + describe(r))
        elif r['kind'] == 'native':
            if r['writer'] in ('test', 'cmdkit'):  # importing ctypes itself opens the process
                out.append('native: ' + describe(r))
        elif r['kind'] in WRITE_KINDS:
            p = r['path']
            if p.startswith('<unresolved'):
                out.append('unresolved: ' + describe(r))
            elif any(under(p, a) for a in allow):
                continue
            elif cache_ok(r, log) or capture_temp(r, log, removed):
                continue
            else:
                out.append('write: ' + describe(r))
    if log['threads_after_main'] != 1:
        out.append(f"threads alive when pytest.main returned: {log['threads_after_main']}")
    for rel in log['changed']:
        if not cache_change(rel):
            out.append(f'changed under the root: {rel}')
    return out


def bookkeeping(path: str, log: dict) -> bool:
    rel = os.path.relpath(path, log['system_tmp'])
    return not rel.startswith('..') and bool(BOOKKEEPING.match(rel))


def by_test(r: dict, log: dict) -> bool:
    if r['kind'] in ('spawn', 'native') or r['path'].startswith('<'):
        return False
    if r['writer'] in TEST_WRITERS:
        mine = True  # (reads are recorded only while a test runs)
    else:
        mine = r['test'] and r['writer'] not in ('import', 'hypothesis') and not bookkeeping(r['path'], log)
    return mine and not cache_ok(r, log)


def cross(opts: argparse.Namespace) -> None:
    logs = []
    for name in opts.logs:
        with open(name) as stream:
            logs.append(json.load(stream))
    touched = [{r['path'] for r in log['records'] if by_test(r, log)} for log in logs]
    written = [{r['path'] for r in log['records'] if by_test(r, log) and r['kind'] in WRITE_KINDS}
               for log in logs]
    bad = []
    for i, w in enumerate(written):
        if not w:
            bad.append(f'run {i + 1}: no test-attributed write recorded (the hook saw nothing)')
    shared = (written[0] & touched[1]) | (written[1] & touched[0])
    bad.extend(f'shared between the runs: {p}' for p in sorted(shared))
    for line in bad:
        print('FAIL R4:', line)
    if bad:
        sys.exit(1)
    print(f'ok cross-run: {len(written[0])} and {len(written[1])} test-written paths, none shared')


def check(opts: argparse.Namespace) -> None:
    with open(opts.log) as stream:
        log = json.load(stream)
    bad = violations(log, opts.allow)
    if log['exit'] != 0:
        bad.append(f"pytest exited {log['exit']}")
    if opts.expect_names:
        with open(opts.expect_names) as stream:
            want = {line.strip() for line in stream if line.strip() and not line.startswith('#')}
        got = {os.path.basename(r['path']) for r in log['records']
               if r['test'] and r['event'] == 'open' and r['kind'] == 'write'
               and r['writer'] in ('test', 'cmdkit')}
        if got != want:
            bad.append(f'file names the tests wrote: missing {sorted(want - got)}, '
                       f'unexpected {sorted(got - want)}')
    writes = sum(1 for r in log['records'] if r['kind'] in WRITE_KINDS)
    for line in bad:
        print('FAIL R1:', line)
    if bad:
        sys.exit(1)
    print(f"ok write audit: {writes} writes recorded, all under {', '.join(opts.allow)} "
          f"or in the tool caches; Python {log['python'].split()[0]}")


# --------------------------------------------------------------------------------------------
# selftest: the hook against a canary suite

CANARY = '''\
import atexit, os, pathlib, shutil, sqlite3, subprocess, sys, tempfile, threading
OUT = {out!r}
SHARED = {shared!r}
SHARED_THREAD = {shared_thread!r}

def j(*parts):
    return os.path.join(OUT, *parts)

def test_inside(tmp_path):
    (tmp_path / 'inside.toml').write_text('x')
    with open(f'{{tmp_path}}/inside.json', mode='w') as stream:
        stream.write('x')

def test_open_w():
    open(j('open_w'), 'w').close()

def test_open_a():
    open(j('open_a'), 'a').close()

def test_open_rplus():
    open(j('open_rplus'), 'r+').close()

def test_os_open():
    os.close(os.open(j('os_open'), os.O_CREAT | os.O_WRONLY))

def test_pathlib():
    pathlib.Path(j('pathlib')).write_text('x')

def test_mkdir():
    os.makedirs(j('mk', 'dirs'))

def test_rename():
    os.rename(j('ren_src'), j('ren_dst'))

def test_replace():
    os.replace(j('rep_src'), j('rep_dst'))

def test_remove():
    os.remove(j('rm_file'))

def test_rmdir():
    os.rmdir(j('rm_dir'))

def test_rmtree():
    shutil.rmtree(j('tree'))

def test_truncate():
    os.truncate(j('trunc'), 0)

def test_utime():
    os.utime(j('utime'))

def test_chmod():
    os.chmod(j('chmod'), 0o644)

def test_fchmod():
    fd = os.open(j('fchmod'), os.O_RDONLY)
    os.fchmod(fd, 0o644)
    os.close(fd)

def test_symlink():
    os.symlink(j('utime'), j('symlink'))

def test_through_symlink(tmp_path):
    os.symlink(j('through'), tmp_path / 'link')
    with open(tmp_path / 'link', 'w') as stream:
        stream.write('x')

def test_hard_link(tmp_path):
    os.link(j('link_src'), tmp_path / 'hard')
    with open(tmp_path / 'hard', 'a') as stream:
        stream.write('x')

def test_dir_fd():
    if os.mkdir not in os.supports_dir_fd:
        return
    fd = os.open(OUT, os.O_RDONLY)
    os.mkdir('dfd_dir', dir_fd=fd)
    os.rename('dfd_dir', 'dfd_dir2', src_dir_fd=fd, dst_dir_fd=fd)
    os.close(fd)

def test_flags():
    if hasattr(os, 'chflags'):
        os.chflags(j('flags'), 0)

def test_sqlite():
    sqlite3.connect(j('db.sqlite')).close()

def test_native():
    import ctypes
    ctypes.CDLL(None)

def test_fork():
    pid = os.fork()
    if pid == 0:
        os._exit(0)
    os.waitpid(pid, 0)

def test_cache_fixture(cache):
    cache.set('canary/counter', 1)

def test_system_tmp():
    fd, name = tempfile.mkstemp()
    os.close(fd)
    os.remove(name)

def test_relative():
    open('relative.txt', 'w').close()

def test_cache_abuse():
    os.makedirs('.hypothesis', exist_ok=True)
    open(os.path.join('.hypothesis', 'abuse'), 'w').close()

def test_spawn_echo():
    assert subprocess.check_output('echo foo-bar', shell=True).strip() == b'foo-bar'

def test_spawn_touch():
    subprocess.check_call('touch spawned.txt', shell=True)

def test_shared():
    with open(SHARED, 'w') as stream:
        stream.write('x')
    with open(SHARED) as stream:
        assert stream.read() == 'x'

def test_shared_thread(tmp_path):
    source = tmp_path / 'source'
    source.write_text('x')
    thread = threading.Thread(target=shutil.copyfile, args=(str(source), SHARED_THREAD))
    thread.start()
    thread.join()

def test_atexit():
    atexit.register(lambda: open(j('atexit'), 'w').close())

def test_zz_late_thread():
    def late():
        import time
        time.sleep(1.0)
        open(j('late'), 'w').close()
    threading.Thread(target=late).start()
'''


def selftest(opts: argparse.Namespace) -> None:
    work = real(opts.work)
    os.makedirs(work, exist_ok=False)
    shared = os.path.join(work, 'shared.txt')
    shared_thread = os.path.join(work, 'shared-thread.txt')
    logs, bad = [], []
    for n in (1, 2):
        out = os.path.join(work, f'out{n}')
        root = os.path.join(work, f'root{n}')
        for d in (out, os.path.join(out, 'rm_dir'), os.path.join(out, 'tree', 'a', 'b'),
                  os.path.join(root, 'tests')):
            os.makedirs(d)
        for name in ('open_rplus', 'ren_src', 'rep_src', 'rm_file', 'trunc', 'utime', 'chmod',
                     'fchmod', 'link_src', 'flags', os.path.join('tree', 'a', 'b', 'f')):
            with open(os.path.join(out, name), 'w') as stream:
                stream.write('x')
        with open(os.path.join(root, 'tests', '__init__.py'), 'w'):
            pass
        with open(os.path.join(root, 'tests', 'test_canary.py'), 'w') as stream:
            stream.write(CANARY.format(out=out, shared=shared, shared_thread=shared_thread))
        log = os.path.join(work, f'canary{n}.json')
        basetemp = os.path.join(work, f'basetemp{n}')
        env = dict(os.environ)
        env['TMPDIR'] = os.path.join(work, 'tmp')
        os.makedirs(env['TMPDIR'], exist_ok=True)
        subprocess.run([sys.executable, '-I', os.path.abspath(__file__), 'run', '--log', log,
                        '--root', root, '--token', f'selftest-{os.getpid()}', '--',
                        '-q', '--basetemp', basetemp],
                       env=env, cwd=root, check=False)
        with open(log) as stream:
            data = json.load(stream)
        logs.append(log)
        found = violations(data, [basetemp])
        text = '\n'.join(found)
        if data['exit'] != 0:
            bad.append(f'canary {n}: pytest exited {data["exit"]} (every canary test should pass)')
        expected = ['open_w', 'open_a', 'open_rplus', 'os_open', 'pathlib', os.path.join('mk', 'dirs'),
                    'ren_src', 'ren_dst', 'rep_src', 'rep_dst', 'rm_file', 'rm_dir', 'tree', 'trunc',
                    'utime', 'chmod', 'fchmod', 'symlink', 'through', 'link_src', 'db.sqlite',
                    'atexit', 'late']
        if os.rmdir in os.supports_dir_fd:  # shutil.rmtree's fd-relative removals resolve
            expected.append(os.path.join('tree', 'a', 'b', 'f'))
        if os.mkdir in os.supports_dir_fd:
            expected.extend(['dfd_dir', 'dfd_dir2'])
        if hasattr(os, 'chflags'):
            expected.append('flags')
        for name in expected:
            target = real(os.path.join(out, name), follow=True)
            if not re.search(r'^write: .* ' + re.escape(target) + r' \(by ', text, re.M):
                bad.append(f'canary {n}: no violation for {target}')
        for target in (real(os.path.join(root, 'relative.txt')),
                       real(os.path.join(root, '.hypothesis', 'abuse')),
                       real(os.path.join(root, '.pytest_cache', 'v', 'canary', 'counter')),
                       real(shared)):
            if not re.search(r'^write: .* ' + re.escape(target) + ' ', text, re.M):
                bad.append(f'canary {n}: no violation for {target}')
        tmp = real(env['TMPDIR'])
        if not re.search(r'^write: open write ' + re.escape(tmp + os.sep) + r'\S+ \(by test', text, re.M):
            bad.append(f'canary {n}: a test\'s temporary file in {tmp} was not reported')
        for pattern, what in ((r'^spawn: .*touch spawned\.txt', 'the touch spawn'),
                              (r'^spawn: os\.fork', 'the fork'),
                              (r'^native: ctypes\.dlopen', 'the native library'),
                              (r'^threads alive when pytest\.main returned: [2-9]', 'the late thread')):
            if not re.search(pattern, text, re.M):
                bad.append(f'canary {n}: {what} was not reported')
        if 'spawned.txt' not in '\n'.join(data['changed']):
            bad.append(f'canary {n}: the listing missed the spawned file')
        if re.search(r'echo foo-bar|inside\.toml|inside\.json', text):
            bad.append(f'canary {n}: an allowed write or spawn was reported:\n{text}')
    proc = subprocess.run([sys.executable, '-I', os.path.abspath(__file__), 'cross'] + logs,
                          capture_output=True, text=True)
    for target in (shared, shared_thread):
        if proc.returncode == 0 or real(target) not in proc.stdout:
            bad.append(f'cross did not report {target}:\n{proc.stdout}{proc.stderr}')
    if 'inside.toml' in proc.stdout or 'pytest-of-' in proc.stdout:
        bad.append(f'cross reported a tmp_path file or pytest bookkeeping as shared:\n{proc.stdout}')
    for line in bad:
        print('FAIL selftest:', line)
    if bad:
        sys.exit(1)
    print(f'ok write-audit selftest: every route reported, allowed writes passed; '
          f'Python {sys.version.split()[0]}')


def main() -> None:
    parser = argparse.ArgumentParser(prog='write_audit.py')
    sub = parser.add_subparsers(dest='mode', required=True)
    p = sub.add_parser('run')
    p.add_argument('--log', required=True)
    p.add_argument('--root', required=True)
    p.add_argument('--token', required=True)
    p.add_argument('--barrier', default='')
    p.add_argument('--peers', type=int, default=2)
    p.add_argument('args', nargs=argparse.REMAINDER)
    p = sub.add_parser('check')
    p.add_argument('log')
    p.add_argument('--allow', action='append', required=True)
    p.add_argument('--expect-names', default='')
    p = sub.add_parser('cross')
    p.add_argument('logs', nargs=2)
    p = sub.add_parser('selftest')
    p.add_argument('--work', required=True)
    opts = parser.parse_args()
    if opts.mode == 'run':
        if opts.args and opts.args[0] == '--':
            opts.args = opts.args[1:]
        run(opts)
    elif opts.mode == 'check':
        check(opts)
    elif opts.mode == 'cross':
        cross(opts)
    else:
        selftest(opts)


if __name__ == '__main__':
    main()
