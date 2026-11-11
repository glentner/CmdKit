# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Drive `Application.main` and `ApplicationGroup.main` in fresh interpreters.

Run with the Python whose environment has the tree under test installed, isolated:

    python -I drive_main.py errors|noargs|all

Every scenario starts its own child interpreter (`sys.executable -I -c ...`), so logging is
exactly as the scenario sets it up and nothing a test runner attaches is present. The child's
exit status is `main`'s return value; its stdout and stderr are captured separately and
compared byte for byte.

Modes:
    errors   argument errors: reported on stderr when no logging is configured, left to the
             configured handlers or the replaced log_critical otherwise, and silent wherever
             Python's last resort would be; the decision is taken per call; importing and
             calling leave the logging handlers as they were.
    noargs   a bare group with and without ALLOW_NOARGS; a bare plain application.
    all      both.

Footprint: one child at a time, each a short-lived interpreter under 40 MB; about 50 children.
"""

# standard libs
import os
import sys
import json
import subprocess

ENV = dict(os.environ)  # a saved copy; the children get this, never a cleared environment
ENV.pop('FORCE_COLOR', None)

PRELUDE = r'''
import sys, json, logging
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError

class Cmd(Application):
    interface = Interface('cmd', 'usage: app cmd ARG [-d]', 'usage: app cmd ARG [-d]\n\nCMD-HELP',
                          disable_colors=True)
    arg: str = None
    interface.add_argument('arg')
    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')
    def run(self):
        print('ran cmd', self.arg)

class Group(ApplicationGroup):
    interface = Interface('app', 'usage: app <command>', 'usage: app <command>\n\nGROUP-HELP',
                          disable_colors=True)
    command: str = None
    interface.add_argument('command')
    commands = {'cmd': Cmd}

class AllowGroup(Group):
    ALLOW_NOARGS = True

class AllowParseGroup(Group):
    ALLOW_NOARGS = True
    ALLOW_PARSE = True

class Outer(ApplicationGroup):
    interface = Interface('outer', 'usage: outer <command>', 'usage: outer <command>\n\nOUTER-HELP',
                          disable_colors=True)
    command: str = None
    interface.add_argument('command')
    commands = {'sub': AllowGroup, 'plain': Group}

class App(Application):
    interface = Interface('solo', 'usage: solo ARG [-d]', 'usage: solo ARG [-d]\n\nSOLO-HELP',
                          disable_colors=True)
    arg: str = None
    interface.add_argument('arg')
    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')
    def run(self):
        print('ran solo', self.arg)

class AllowApp(App):
    ALLOW_NOARGS = True

class Interrupted(App):
    def run(self):
        raise KeyboardInterrupt()

class Bare(Application):
    interface = Interface('bare', 'usage: bare [-d]', 'usage: bare [-d]\n\nBARE-HELP',
                          disable_colors=True)
    ALLOW_NOARGS = True
    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')
    def run(self):
        print('ran bare')

calls = []
def recorder(error):
    calls.append(str(error))
'''

FAILURES = []


def child(body: str, pre: str = '') -> subprocess.CompletedProcess:
    """Run `pre`, the shared prelude, then `body` in a fresh isolated interpreter."""
    code = pre + '\n' + PRELUDE + '\n' + body
    return subprocess.run([sys.executable, '-I', '-c', code], env=ENV,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)


def check(name: str, ok: bool, detail: str) -> None:
    print(('ok    ' if ok else 'FAIL  ') + name + ('' if ok else ': ' + detail))
    if not ok:
        FAILURES.append(name)


def expect(app: str, argv: list) -> str:
    """The ArgumentError message `app.from_cmdline(argv)` raises, from its own child."""
    proc = child(f'''
try:
    {app}.from_cmdline({argv!r})
except ArgumentError as error:
    sys.stdout.write(json.dumps(str(error)))
else:
    sys.stdout.write(json.dumps(None))
''')
    if proc.returncode != 0:
        return None
    return json.loads(proc.stdout.decode())


def run_main(call: str, pre: str = '', body_pre: str = '', post: str = '') -> subprocess.CompletedProcess:
    """A child that exits with the status `call` returns."""
    return child(f'''
{body_pre}
status = {call}
{post}
sys.exit(status)
''', pre=pre)


def show(proc: subprocess.CompletedProcess) -> str:
    return f'status={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}'


def errors() -> None:
    """Argument errors with logging unconfigured, configured, or log_critical replaced."""

    # Unconfigured: the message alone and a newline, once, on stderr; stdout empty; status 2.
    cases = [
        ('unknown command in a group', 'Group', ['bogus'], 'Group', ['bogus'], 'bogus'),
        ('unknown flag, top level', 'App', ['x', '--bogus'], 'App', ['x', '--bogus'], '--bogus'),
        ('missing positional, top level', 'App', ['--debug'], 'App', ['--debug'], 'arg'),
        ('unknown flag in a group command', 'Group', ['cmd', 'x', '--bogus'], 'Cmd', ['x', '--bogus'], '--bogus'),
        ('missing positional in a group command', 'Group', ['cmd', '--debug'], 'Cmd', ['--debug'], 'arg'),
        ('nested group, unknown command', 'Outer', ['plain', 'bogus'], 'Group', ['bogus'], 'bogus'),
        ('ALLOW_NOARGS application, bare, missing positional', 'AllowApp', [], 'App', [], 'arg'),
    ]
    for name, app, argv, source, source_argv, token in cases:
        if source == 'Group' and source_argv == ['bogus']:
            message = 'unrecognized command: bogus'  # raised by ApplicationGroup.run, not the parser
        else:
            message = expect(source, source_argv)
        if not message or token not in message:
            check(f'unconfigured: {name}', False, f'expected message not derivable: {message!r}')
            continue
        proc = run_main(f'{app}.main({argv!r})')
        check(f'unconfigured: {name}',
              proc.returncode == 2 and proc.stdout == b'' and proc.stderr == (message + '\n').encode(),
              show(proc))

    # Configured before import: basicConfig on the root logger gets one CRITICAL record and
    # cmdkit writes nothing of its own.
    fmt = 'import logging; logging.basicConfig(format="%(levelname)s|%(name)s|%(message)s")'
    proc = run_main("Group.main(['bogus'])", pre=fmt)
    check('basicConfig: one formatted line, nothing bare',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'CRITICAL|cmdkit.app|unrecognized command: bogus\n', show(proc))
    proc = run_main("Group.main(['cmd', 'x', '--bogus'])", pre=fmt)
    lines = proc.stderr.decode().splitlines()
    check('basicConfig: an error inside a group command is logged once',
          proc.returncode == 2 and proc.stdout == b'' and len(lines) == 1
          and lines[0].startswith('CRITICAL|cmdkit.app|') and '--bogus' in lines[0], show(proc))

    # A handler on cmdkit's own logger, beside its NullHandler: it receives the one record.
    proc = run_main("Group.main(['bogus'])", body_pre='''
class Keep(logging.Handler):
    def emit(self, record):
        calls.append((record.levelname, record.name, record.getMessage()))
logging.getLogger('cmdkit').addHandler(Keep())
''', post='sys.stdout.write(json.dumps(calls))')
    check('handler on the cmdkit logger: one CRITICAL record, stderr empty',
          proc.returncode == 2 and proc.stderr == b''
          and json.loads(proc.stdout.decode() or 'null') == [['CRITICAL', 'cmdkit.app', 'unrecognized command: bogus']],
          show(proc))

    # A NullHandler the application puts on the root logger is a handler other than cmdkit's.
    proc = run_main("Group.main(['bogus'])", body_pre='logging.getLogger().addHandler(logging.NullHandler())')
    check('application NullHandler on root: cmdkit stays silent',
          proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))

    # The last-resort rule: cmdkit writes exactly when Python's last-resort handler would print
    # the record were cmdkit's NullHandler not there. Whatever silences it stays silent.
    dict_config = ("import logging.config; logging.config.dictConfig({'version': 1, %s"
                   "'formatters': {'f': {'format': 'H|%%(message)s'}}, "
                   "'handlers': {'h': {'class': 'logging.StreamHandler', 'formatter': 'f'}}, "
                   "'root': {'handlers': ['h']}})")
    silent = [
        ('dictConfig after import, disable_existing_loggers left True', dict_config % ''),
        ('logging.disable(CRITICAL)', 'logging.disable(logging.CRITICAL)'),
        ('only a root handler with a level above CRITICAL',
         'h = logging.StreamHandler(); h.setLevel(logging.CRITICAL + 1); logging.getLogger().addHandler(h)'),
        ('cmdkit.app logger level above CRITICAL', "logging.getLogger('cmdkit.app').setLevel(logging.CRITICAL + 1)"),
        ('logging.lastResort set to None', 'logging.lastResort = None'),
        ('logging.lastResort level above CRITICAL', 'logging.lastResort.setLevel(logging.CRITICAL + 1)'),
    ]
    for name, setup in silent:
        proc = run_main("Group.main(['bogus'])", body_pre=setup)
        check(f'last resort silenced, cmdkit silent: {name}',
              proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre=(
        "logging.getLogger('cmdkit.app').setLevel(logging.ERROR); logging.lastResort.setLevel(logging.ERROR)"))
    check('cmdkit.app and the last resort at ERROR: a CRITICAL record still prints, bare',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre=dict_config % "'disable_existing_loggers': False, ")
    check('dictConfig with disable_existing_loggers False: its one formatted line, nothing bare',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'H|unrecognized command: bogus\n', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre=(
        "logging.basicConfig(format='%(levelname)s|%(message)s'); logging.getLogger('cmdkit').propagate = False"))
    check('cmdkit.propagate False, root configured: the bare line once, as Python would',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))

    # log_critical replaced: on the class, on Application, and by another logger's method.
    proc = run_main("Group.main(['bogus'])", body_pre='Group.log_critical = staticmethod(recorder)',
                    post='sys.stdout.write(json.dumps(calls))')
    check('log_critical replaced on the class: called once, stderr empty',
          proc.returncode == 2 and proc.stderr == b''
          and json.loads(proc.stdout.decode() or 'null') == ['unrecognized command: bogus'], show(proc))
    proc = run_main("Group.main(['cmd', 'x', '--bogus'])", body_pre='Application.log_critical = recorder',
                    post='sys.stdout.write(json.dumps(calls))')
    got = json.loads(proc.stdout.decode() or 'null')
    check('log_critical replaced on Application: called once, stderr empty',
          proc.returncode == 2 and proc.stderr == b'' and isinstance(got, list) and len(got) == 1
          and '--bogus' in got[0], show(proc))
    proc = run_main("Group.main(['bogus'])",
                    body_pre="Application.log_critical = logging.getLogger('elsewhere').critical")
    check("log_critical replaced by another logger's critical: Python's own last resort only",
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))

    # Decided per call: unconfigured, then configured, then unconfigured again.
    proc = child('''
first = Group.main(['bogus'])
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(logging.Formatter('%(levelname)s|%(message)s'))
logging.getLogger().addHandler(handler)
second = Group.main(['bogus'])
logging.getLogger().removeHandler(handler)
third = Group.main(['bogus'])
sys.exit(0 if (first, second, third) == (2, 2, 2) else 1)
''')
    check('decided per call: bare, handled, bare',
          proc.returncode == 0 and proc.stdout == b''
          and proc.stderr == (b'unrecognized command: bogus\n'
                              b'CRITICAL|unrecognized command: bogus\n'
                              b'unrecognized command: bogus\n'), show(proc))

    # Out of this change: the keyboard-interrupt message stays as it is (silent when unconfigured).
    proc = run_main("Interrupted.main(['x'])")
    check('keyboard interrupt: status 4, nothing written, as in 2.7.7',
          proc.returncode == 4 and proc.stdout == b'' and proc.stderr == b'', show(proc))

    # Footprint: the handlers on cmdkit, cmdkit.app and root after import, and after a call
    # that reports an error on stderr, are those 2.7.7 has (measured at b9efaca).
    proc = child('''
def snap():
    out = {}
    for name in ('cmdkit', 'cmdkit.app', ''):
        logger = logging.getLogger(name)
        out[name or 'root'] = [[type(h).__module__, type(h).__name__, id(h)] for h in logger.handlers]
    out['lastResort'] = [type(logging.lastResort).__name__, id(logging.lastResort)]
    out['stderr'] = sys.stderr is sys.__stderr__
    return out
before = snap()
Group.main(['bogus'])
App.main(['x', '--bogus'])
after = snap()
sys.stdout.write(json.dumps([before, after]))
''', pre='import logging')
    try:
        before, after = json.loads(proc.stdout.decode())
        shape = {k: [h[:2] for h in v] for k, v in before.items() if k in ('cmdkit', 'cmdkit.app', 'root')}
        ok = (shape == {'cmdkit': [['logging', 'NullHandler']], 'cmdkit.app': [], 'root': []}
              and before == after and before['stderr'] is True)
        detail = f'before={before} after={after}'
    except ValueError:
        ok, detail = False, show(proc)
    check('footprint: handlers after import and after a reported error are 2.7.7\'s', ok, detail)


def noargs() -> None:
    """A bare group, with and without ALLOW_NOARGS, and a bare plain application."""
    helped = run_main("AllowGroup.main(['--help'])")
    check('reference: the group\'s --help', helped.returncode == 0 and b'GROUP-HELP' in helped.stdout
          and helped.stderr == b'', show(helped))
    for call in ('AllowGroup.main([])', 'AllowGroup.main(None)', 'AllowGroup.main()'):
        proc = run_main(call)
        check(f'opt-in: {call} prints --help and returns 0',
              proc.returncode == 0 and proc.stdout == helped.stdout and proc.stderr == b'', show(proc))
    helped_parse = run_main("AllowParseGroup.main(['--help'])")
    proc = run_main('AllowParseGroup.main([])')
    check('opt-in with ALLOW_PARSE: main([]) prints --help and returns 0',
          proc.returncode == 0 and proc.stdout == helped_parse.stdout and b'GROUP-HELP' in proc.stdout
          and proc.stderr == b'', show(proc))
    proc = run_main("Outer.main(['sub'])")
    check('opt-in as a nested command: bare sub-group prints its --help and returns 0',
          proc.returncode == 0 and proc.stdout == helped.stdout and proc.stderr == b'', show(proc))

    usage = b'usage: app <command>\n'
    for call in ('Group.main([])', 'Group.main(None)', "Outer.main(['plain'])"):
        proc = run_main(call)
        check(f'default: {call} prints usage and returns 1',
              proc.returncode == 1 and proc.stdout == usage and proc.stderr == b'', show(proc))
    proc = run_main('App.main([])')
    check('plain application, default: usage and 1',
          proc.returncode == 1 and proc.stdout == b'usage: solo ARG [-d]\n' and proc.stderr == b'', show(proc))
    proc = run_main('Bare.main([])')
    check('plain application, ALLOW_NOARGS: runs and returns 0',
          proc.returncode == 0 and proc.stdout == b'ran bare\n' and proc.stderr == b'', show(proc))


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ''
    if mode not in ('errors', 'noargs', 'all'):
        print('usage: drive_main.py errors|noargs|all')
        return 2
    print(f'== drive_main {mode} on Python {sys.version.split()[0]}')
    if mode in ('errors', 'all'):
        errors()
    if mode in ('noargs', 'all'):
        noargs()
    if FAILURES:
        print(f'FAIL: {len(FAILURES)} check(s) failed')
        return 1
    print('ok: all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
