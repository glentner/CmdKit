# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Mutant sweep: every decision in the argument-error report and the bare-group help, each mutant
killed by tests/test_app.py alone (review cycle 1, finding F5).

Run with the Python whose environment has the export installed editable, from the export:

    python -I mutants.py EXPORT P1|P2

P1 sweeps the report's decisions (the helper and its call site in Application.main); P2 adds
the bare group's (ApplicationGroup.main), whose lines P1's tree does not hold yet. Each mutant is an exact text replacement in EXPORT/src/cmdkit/app.py. Its anchor must occur
exactly once, or the sweep fails (a missing anchor is a red, never a skip): the anchors are the
lines PLAN.md § 2 gives verbatim. For each mutant the file is rewritten, tests/test_app.py runs
in a child interpreter with a fresh bytecode prefix (so no stale .pyc can stand in for the
mutant), and the file is restored. A mutant is killed when pytest exits 1 (tests failed) and at
least one failing test is one that pins its behaviour: a test named `test_app_argument_error_*`
or `test_app_noargs_allowed_*` for the report's decisions, `test_app_group_*` for the bare
group's (a failure only elsewhere, such as a test that reads the module's source, does not
count). Exit 0 is a survivor, and anything else (a collection or usage error) a broken mutant:
both red. The unmutated tree must pass first, and the file must be byte-identical to it at the
end. (Adversarial review of the revised plan: the killer set, the probe record's contents, the
replacement's identity, and the bare group's command line read from sys.argv.)

Footprint: one pytest child at a time, under 100 MB; about 1 s per mutant warm.
"""

# standard libs
import os
import sys
import tempfile
import subprocess

HELPER = [
    ('enabled check removed',
     '    if not logger.isEnabledFor(level):\n        return False\n', ''),
    ('enabled check reads only logger.disabled',
     '    if not logger.isEnabledFor(level):\n', '    if logger.disabled:\n'),
    ('probe record carries no message',
     "    if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, msg, (), None)):\n",
     "    if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, '', (), None)):\n"),
    ('probe record at DEBUG',
     "    if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, msg, (), None)):\n",
     "    if not logger.filter(logger.makeRecord(logger.name, logging.DEBUG, '(unknown file)', 0, msg, (), None)):\n"),
    ('probe record named cmdkit',
     "    if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, msg, (), None)):\n",
     "    if not logger.filter(logger.makeRecord('cmdkit', level, '(unknown file)', 0, msg, (), None)):\n"),
    ('filter check removed',
     "    if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, msg, (), None)):\n"
     "        return False\n", ''),
    ('lastResort presence check removed',
     '    if logging.lastResort is None or level < logging.lastResort.level:\n',
     '    if level < logging.lastResort.level:\n'),
    ('lastResort level check removed',
     '    if logging.lastResort is None or level < logging.lastResort.level:\n',
     '    if logging.lastResort is None:\n'),
    ('lastResort level boundary moved (< to <=)',
     '    if logging.lastResort is None or level < logging.lastResort.level:\n',
     '    if logging.lastResort is None or level <= logging.lastResort.level:\n'),
    ('propagate walk does not stop',
     '        if not current.propagate:\n            break\n', ''),
    ('handler levels counted (the overruled reading)',
     '        for handler in current.handlers:\n',
     '        for handler in current.handlers:\n            if level < handler.level:\n                continue\n'),
    ('any NullHandler anywhere counts as cmdkit\'s',
     "            if current.name != 'cmdkit' or type(handler) is not logging.NullHandler:\n",
     '            if type(handler) is not logging.NullHandler:\n'),
    ('a NullHandler subclass counts as cmdkit\'s',
     "            if current.name != 'cmdkit' or type(handler) is not logging.NullHandler:\n",
     "            if current.name != 'cmdkit' or not isinstance(handler, logging.NullHandler):\n"),
    ('cmdkit\'s NullHandler looked for on cmdkit.app',
     "            if current.name != 'cmdkit' or type(handler) is not logging.NullHandler:\n",
     "            if current.name != 'cmdkit.app' or type(handler) is not logging.NullHandler:\n"),
    ('cmdkit\'s NullHandler counted as the application\'s',
     "            if current.name != 'cmdkit' or type(handler) is not logging.NullHandler:\n",
     '            if True:\n'),
    ('no handler at all still writes (F1)',
     '    return found\n', '    return True\n'),
    ('cmdkit\'s NullHandler alone never writes',
     '    return found\n', '    return False\n'),
]

CALL_SITE = [
    ('replacement check removed',
     '            if cls.log_critical == log.critical and _hidden_by_null_handler(log, logging.CRITICAL, error):\n',
     '            if _hidden_by_null_handler(log, logging.CRITICAL, error):\n'),
    ('replacement compared by function only',
     '            if cls.log_critical == log.critical and _hidden_by_null_handler(log, logging.CRITICAL, error):\n',
     "            if getattr(cls.log_critical, '__func__', None) is logging.Logger.critical"
     ' and _hidden_by_null_handler(log, logging.CRITICAL, error):\n'),
    ('level argument changed to WARNING',
     '            if cls.log_critical == log.critical and _hidden_by_null_handler(log, logging.CRITICAL, error):\n',
     '            if cls.log_critical == log.critical and _hidden_by_null_handler(log, logging.WARNING, error):\n'),
    ('written to stdout',
     '                print(error, file=sys.stderr)\n', '                print(error)\n'),
]

BARE_GROUP = [
    ('bare group: the parse check removed (help on every bare run)',
     '            try:\n                cls.interface.parse_args(cmdline)\n            except ArgumentError:\n'
     "                cmdline = ['--help', ]\n",
     "            cmdline = ['--help', ]\n"),
    ('bare group: help when the parse succeeds',
     '            try:\n                cls.interface.parse_args(cmdline)\n            except ArgumentError:\n'
     "                cmdline = ['--help', ]\n",
     "            try:\n                cls.interface.parse_args(cmdline)\n                cmdline = ['--help', ]\n"
     '            except ArgumentError:\n                pass\n'),
    ('bare group: the probe parses [] in place of the command line (None ignores sys.argv)',
     '                cls.interface.parse_args(cmdline)\n            except ArgumentError:\n',
     '                cls.interface.parse_args([])\n            except ArgumentError:\n'),
    ('bare group: the opt-in ignored',
     '        if not cmdline and cls.ALLOW_NOARGS is True:\n            try:\n',
     '        if not cmdline:\n            try:\n'),
]

KILLERS = {'report': ('test_app_argument_error_', 'test_app_noargs_allowed_'), 'group': ('test_app_group_', )}

REPORT = [(name, anchor, new, 'report') for name, anchor, new in HELPER + CALL_SITE]
GROUP = [(name, anchor, new, 'group') for name, anchor, new in BARE_GROUP]
PHASES = {'P1': REPORT, 'P2': REPORT + GROUP}


def pytest(export: str, prefix: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, '-X', f'pycache_prefix={prefix}', '-m', 'pytest', '-q',
                           '-p', 'no:cacheprovider', '--hypothesis-seed=0', 'tests/test_app.py'],
                          cwd=export, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)


def failed_tests(output: str) -> list:
    """The test names (no module, no parameters) pytest reports FAILED."""
    names = []
    for line in output.splitlines():
        if line.startswith('FAILED '):
            names.append(line[len('FAILED '):].split(' - ')[0].split('::')[-1])
    return names


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[2] not in PHASES:
        print('usage: mutants.py EXPORT P1|P2')
        return 2
    export, phase = sys.argv[1], sys.argv[2]
    mutants = PHASES[phase]
    target = os.path.join(export, 'src', 'cmdkit', 'app.py')
    with open(target, encoding='utf-8') as stream:
        original = stream.read()
    work = tempfile.mkdtemp(prefix='cli-defaults-mutants.', dir=os.environ.get('TMPDIR'))
    print(f'== mutants {phase} on Python {sys.version.split()[0]}: {len(mutants)} mutants, bytecode under {work}')

    failures = []
    proc = pytest(export, os.path.join(work, 'baseline'))
    if proc.returncode != 0:
        print('FAIL  baseline: tests/test_app.py does not pass unmutated')
        print(proc.stdout.decode()[-2000:])
        return 1
    print('ok    baseline: tests/test_app.py passes unmutated')

    try:
        for number, (name, anchor, replacement, family) in enumerate(mutants, start=1):
            label = f'M{number:02d} {name}'
            count = original.count(anchor)
            if count != 1:
                print(f'FAIL  {label}: anchor found {count} times, expected once')
                failures.append(label)
                continue
            with open(target, 'w', encoding='utf-8') as stream:
                stream.write(original.replace(anchor, replacement))
            try:
                proc = pytest(export, os.path.join(work, f'm{number:02d}'))
            finally:
                with open(target, 'w', encoding='utf-8') as stream:
                    stream.write(original)
            output = proc.stdout.decode()
            failed = failed_tests(output)
            pinned = sorted({t for t in failed if t.startswith(KILLERS[family])})
            if proc.returncode == 1 and pinned:
                more = f' (+{len(pinned) - 1} more)' if len(pinned) > 1 else ''
                print(f'ok    {label}: killed by {pinned[0]}{more}')
            elif proc.returncode == 1:
                print(f'FAIL  {label}: killed only by tests outside {KILLERS[family]}: {failed}')
                failures.append(label)
            elif proc.returncode == 0:
                print(f'FAIL  {label}: survived')
                failures.append(label)
            else:
                print(f'FAIL  {label}: broken mutant, pytest exit {proc.returncode}')
                print(output[-1500:])
                failures.append(label)
    finally:
        with open(target, encoding='utf-8') as stream:
            restored = stream.read() == original
    if not restored:
        print('FAIL  src/cmdkit/app.py not restored')
        failures.append('restore')
    if failures:
        print(f'FAIL: {len(failures)} mutant(s) not killed')
        return 1
    print(f'ok: all {len(mutants)} mutants killed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
