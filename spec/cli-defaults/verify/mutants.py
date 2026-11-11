# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Mutant sweep: every decision in the argument-error report, each mutant killed by
tests/test_app.py alone (review cycle 1, finding F5; review cycle 2, finding F3).

Run with the Python whose environment has the export installed editable, from the export:

    python -I mutants.py EXPORT P1|P2

P1 and P2 sweep the same mutants: the bare-group help left the cycle (GOAL C9), and with it the
bare group's mutants. Each mutant is an exact text replacement in one file of EXPORT:
src/cmdkit/app.py (the helper and its call site in Application.main) or src/cmdkit/__init__.py
(the mark on cmdkit's own NullHandler). Its anchor must occur exactly once in that file, or the
sweep fails (a missing anchor is a red, never a skip): the anchors are the lines PLAN.md § 2 gives
verbatim. For each mutant the file is rewritten, tests/test_app.py runs in a child interpreter
with a fresh bytecode prefix (passed as -X pycache_prefix and as PYTHONPYCACHEPREFIX, so the
suite's own child interpreters see the mutant too, and no stale .pyc can stand in for it), and the
file is restored. A mutant is killed when pytest exits 1 (tests failed) and at least one failing
test is one that pins the report: a test named test_app_argument_error_* or
test_app_noargs_allowed_* (a failure only elsewhere, such as a test that reads the module's
source, does not count). Exit 0 is a survivor, and anything else (a collection or usage error) a
broken mutant: both red. The unmutated tree must pass first, and both files must be
byte-identical to it at the end.

Before the mutants, a control run appends a comment line to each target file: a test that fails on
that is pinning the source text, not the behaviour, and the sweep is red (adversarial review of the
C9 revision: a pin test would otherwise "kill" every mutant).

Footprint: one pytest child at a time (and the suite's one short-lived child), under 100 MB;
about 1 s per mutant warm.
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
    ('only the last handler on each logger looked at',
     '        for handler in current.handlers:\n', '        for handler in current.handlers[-1:]:\n'),
    ('only the first handler on each logger looked at',
     '        for handler in current.handlers:\n', '        for handler in current.handlers[:1]:\n'),
    ('propagate walk does not stop',
     '        if not current.propagate:\n            break\n', ''),
    ('handler levels counted (the overruled reading)',
     '        for handler in current.handlers:\n',
     '        for handler in current.handlers:\n            if level < handler.level:\n                continue\n'),
    ('the mark ignored: any plain NullHandler counts as cmdkit\'s (review cycle 2, F3)',
     "            if getattr(handler, '_cmdkit_library_handler', False) is not True:\n",
     '            if type(handler) is not logging.NullHandler:\n'),
    ('the mark ignored: any NullHandler on the cmdkit logger counts (review cycle 2, F3)',
     "            if getattr(handler, '_cmdkit_library_handler', False) is not True:\n",
     "            if current.name != 'cmdkit' or not isinstance(handler, logging.NullHandler):\n"),
    ('an unmarked handler counts as cmdkit\'s (the mark defaults to true)',
     "            if getattr(handler, '_cmdkit_library_handler', False) is not True:\n",
     "            if getattr(handler, '_cmdkit_library_handler', True) is not True:\n"),
    ('cmdkit\'s marked NullHandler counted as the application\'s',
     "            if getattr(handler, '_cmdkit_library_handler', False) is not True:\n",
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

INIT = [
    ('the mark not set where cmdkit attaches its NullHandler (review cycle 2, F3)',
     '_null_handler._cmdkit_library_handler = True\n', ''),
    ('the mark set to a truthy value other than True',
     '_null_handler._cmdkit_library_handler = True\n', '_null_handler._cmdkit_library_handler = 1\n'),
]

KILLERS = ('test_app_argument_error_', 'test_app_noargs_allowed_')

MUTANTS = ([('src/cmdkit/app.py', name, anchor, new) for name, anchor, new in HELPER + CALL_SITE]
           + [('src/cmdkit/__init__.py', name, anchor, new) for name, anchor, new in INIT])
PHASES = {'P1': MUTANTS, 'P2': MUTANTS}


ENV = dict(os.environ)  # a saved copy; each child gets it with its own bytecode prefix


def pytest(export: str, prefix: str) -> subprocess.CompletedProcess:
    env = dict(ENV, PYTHONPYCACHEPREFIX=prefix)
    return subprocess.run([sys.executable, '-X', f'pycache_prefix={prefix}', '-m', 'pytest', '-q',
                           '-p', 'no:cacheprovider', '--hypothesis-seed=0', 'tests/test_app.py'],
                          cwd=export, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)


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
    originals = {}
    for rel in sorted({rel for rel, *_ in mutants}):
        with open(os.path.join(export, rel), encoding='utf-8') as stream:
            originals[rel] = stream.read()
    work = tempfile.mkdtemp(prefix='cli-defaults-mutants.', dir=os.environ.get('TMPDIR'))
    print(f'== mutants {phase} on Python {sys.version.split()[0]}: {len(mutants)} mutants, bytecode under {work}')

    failures = []
    proc = pytest(export, os.path.join(work, 'baseline'))
    if proc.returncode != 0:
        print('FAIL  baseline: tests/test_app.py does not pass unmutated')
        print(proc.stdout.decode()[-2000:])
        return 1
    print('ok    baseline: tests/test_app.py passes unmutated')

    for rel, original in originals.items():
        target = os.path.join(export, rel)
        with open(target, 'w', encoding='utf-8') as stream:
            stream.write(original + '# control: a comment changes no behaviour\n')
        try:
            proc = pytest(export, os.path.join(work, 'control-' + rel.replace('/', '-')))
        finally:
            with open(target, 'w', encoding='utf-8') as stream:
                stream.write(original)
        if proc.returncode != 0:
            print(f'FAIL  control: a comment added to {rel} fails tests that pin its text: '
                  f'{failed_tests(proc.stdout.decode())}')
            failures.append('control ' + rel)
        else:
            print(f'ok    control: a comment added to {rel} fails nothing')

    try:
        for number, (rel, name, anchor, replacement) in enumerate(mutants, start=1):
            label = f'M{number:02d} {name}'
            target, original = os.path.join(export, rel), originals[rel]
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
            pinned = sorted({t for t in failed if t.startswith(KILLERS)})
            if proc.returncode == 1 and pinned:
                more = f' (+{len(pinned) - 1} more)' if len(pinned) > 1 else ''
                print(f'ok    {label}: killed by {pinned[0]}{more}')
            elif proc.returncode == 1:
                print(f'FAIL  {label}: killed only by tests outside {KILLERS}: {failed}')
                failures.append(label)
            elif proc.returncode == 0:
                print(f'FAIL  {label}: survived')
                failures.append(label)
            else:
                print(f'FAIL  {label}: broken mutant, pytest exit {proc.returncode}')
                print(output[-1500:])
                failures.append(label)
    finally:
        restored = []
        for rel, original in originals.items():
            with open(os.path.join(export, rel), encoding='utf-8') as stream:
                restored.append(stream.read() == original)
    if not all(restored):
        print('FAIL  a mutated file was not restored')
        failures.append('restore')
    if failures:
        print(f'FAIL: {len(failures)} mutant(s) not killed')
        return 1
    print(f'ok: all {len(mutants)} mutants killed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
