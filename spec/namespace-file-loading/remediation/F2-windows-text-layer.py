"""Checker for review cycle 1, F2: the tests this cycle adds hold under Windows' text layer.

    python -I F2-windows-text-layer.py run [PYTEST ARGS ...]
        Run inside the profile's environment for the index (the launcher runs it on 3.9 and 3.14).
        It runs pytest in this process with a plugin that approximates a Windows CI runner without
        UTF-8 mode, only while each test body runs: `builtins.open` and `io.open` become the
        pure-Python `_pyio.open`, which honours `os.linesep` and the locale functions;
        `os.linesep` is '\\r\\n'; the locale encoding is cp1252. Binary I/O is unaffected. The same
        emulation as the review's (`winsim.py`, review cycle 1). Before the first test body it checks
        that the emulation is live: a text-mode write of '\\n' lands as b'\\r\\n', and a text-mode
        file opened with no encoding reports cp1252.

    The launcher then reads the run's `-rA` summary: every test of TestFileLoading in NAMED PASSED,
    none is missing, and nothing in the run FAILED, ERRORED or was SKIPPED.

Footprint: one pytest process, under 150 MB; a few seconds.
"""

# type annotations
from __future__ import annotations

# standard libs
import io
import os
import re
import sys
import _pyio
import locale
import builtins
import tempfile

NAMED = ['test_path_round_trip', 'test_path_ignore_if_missing', 'test_configuration_path_layers',
         'test_loader_error_propagates', 'test_writer_error_propagates', 'test_unsupported_extension',
         'test_toml_binary_handle', 'test_toml_text_handle', 'test_toml_handle_of_any_class',
         'test_decode_error_names_file', 'test_decode_error_configuration',
         'test_decode_error_handle_unchanged', 'test_other_errors_unchanged']
SUMMARY = re.compile(r'^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (\S+)')


class WindowsTextLayer:
    """The Windows text layer, during each test call only; `install` gives the pytest plugin."""

    def __init__(self) -> None:
        self.checked = False

    def _canary(self) -> None:
        handle, name = tempfile.mkstemp(prefix='nfl-f2-')
        os.close(handle)
        try:
            with open(name, 'w') as stream:
                encoding = stream.encoding
                stream.write('\n')
            with io.FileIO(name) as stream:
                data = stream.read()
        finally:
            os.unlink(name)
        if data != b'\r\n' or encoding.lower() != 'cp1252':
            raise SystemExit(f'FAIL: the emulation is not live: wrote {data!r}, encoding {encoding!r}')
        print(f'\nemulation live: a text-mode newline lands as {data!r}, the default encoding is {encoding}')
        self.checked = True

    def install(self):
        import pytest

        plugin = self

        class Hooks:
            @pytest.hookimpl(hookwrapper=True)
            def pytest_runtest_call(self, item):
                saved = (builtins.open, io.open, os.linesep, locale.getpreferredencoding,
                         getattr(locale, 'getencoding', None))
                builtins.open = io.open = _pyio.open
                os.linesep = '\r\n'
                locale.getpreferredencoding = lambda do_setlocale=True: 'cp1252'
                if saved[4] is not None:
                    locale.getencoding = lambda: 'cp1252'
                try:
                    if not plugin.checked:
                        plugin._canary()
                    yield
                finally:
                    builtins.open, io.open, os.linesep, locale.getpreferredencoding = saved[:4]
                    if saved[4] is not None:
                        locale.getencoding = saved[4]
        return Hooks()


def check(path: str) -> None:
    passed, bad = set(), []
    with open(path) as stream:
        text = stream.read()
    if 'emulation live:' not in text:
        bad.append('the emulation canary did not run')
    for line in text.splitlines():
        m = SUMMARY.match(line)
        if m:
            (passed.add(m.group(2)) if m.group(1) == 'PASSED' else bad.append(line.strip()[:160]))
    for name in NAMED:
        node = f'tests/test_config.py::TestFileLoading::{name}'
        if not any(n == node or n.startswith(node + '[') for n in passed):
            bad.append(f'not PASSED: {node}')
    for line in bad:
        print('FAIL:', line)
    if bad:
        sys.exit(1)
    print(f'ok F2: {len(NAMED)} TestFileLoading tests and {len(passed)} in all pass under the Windows text layer')


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ['run']:
        import pytest
        sys.exit(pytest.main(args[1:], plugins=[WindowsTextLayer().install()]))
    elif len(args) == 2 and args[0] == 'check':
        check(args[1])
    else:
        print('usage: F2-windows-text-layer.py run [PYTEST ARGS ...] | check OUTPUT')
        sys.exit(2)


if __name__ == '__main__':
    main()
