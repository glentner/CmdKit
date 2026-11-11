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
             calling leave the logging handlers as they were. Review cycle 1: where no handler
             is found at all, Python's last resort prints the line and cmdkit adds nothing
             (finding F1, every error target); a filter on cmdkit.app that rejects the record
             keeps it silent (finding F3), and the filter sees the record's message, level and
             logger name (adversarial review of the revised plan). Review cycle 2, F3: only the
             NullHandler cmdkit's __init__ marks counts as cmdkit's; an application's own
             NullHandler on the cmdkit logger, added or configured by dictConfig, keeps it
             silent; a second marked one (a reload) does not.
    noargs   a bare group behaves exactly as in 2.7.7, apart from R1 reporting its argument
             errors (GOAL C9): groups that require or take an optional command, with and without
             ALLOW_NOARGS, with ALLOW_PARSE, with an exceptions map, nested; main([]), main() and
             main(None) with sys.argv empty, an unknown command, an unknown flag, extra
             arguments, a command, --help, --version and an action that raises (review cycle 2,
             F1 and F2, pinned to 2.7.7). A bare plain application, as before.
    all      both.

Footprint: one child at a time, each a short-lived interpreter under 40 MB; about 150 children.
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
    interface.add_argument('-v', '--version', action='version', version='9.9.9')
    commands = {'cmd': Cmd}

class AllowGroup(Group):
    ALLOW_NOARGS = True

class AllowParseGroup(Group):
    ALLOW_NOARGS = True
    ALLOW_PARSE = True

class OptGroup(ApplicationGroup):
    interface = Interface('opt', 'usage: opt [<command>]', 'usage: opt [<command>]\n\nOPT-HELP',
                          disable_colors=True)
    command: str = None
    interface.add_argument('command', nargs='?', default=None)
    interface.add_argument('-v', '--version', action='version', version='9.9.9')
    commands = {'cmd': Cmd}
    def run(self):
        if self.command is None:
            print('default action')
        else:
            super().run()

class AllowOptGroup(OptGroup):
    ALLOW_NOARGS = True

import argparse

class Boom(Exception):
    pass

class BoomAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        raise Boom('boom')

class BoomGroup(ApplicationGroup):
    interface = Interface('boom', 'usage: boom <command>', 'usage: boom <command>\n\nBOOM-HELP',
                          disable_colors=True)
    command: str = None
    interface.add_argument('command')
    interface.add_argument('--boom', nargs=0, action=BoomAction)
    commands = {'cmd': Cmd}
    ALLOW_NOARGS = True
    exceptions = {**ApplicationGroup.exceptions, Boom: (lambda error: 7)}

class TruthyGroup(Group):
    ALLOW_NOARGS = 1

class SharedOpt(OptGroup):
    ALLOW_NOARGS = True
    def run(self):
        print('shared', None if self.shared is None else dict(self.shared))

class ParseOuter(ApplicationGroup):
    interface = Interface('pouter', 'usage: pouter <command>', 'usage: pouter <command>\n\nPOUTER-HELP',
                          disable_colors=True)
    command: str = None
    interface.add_argument('command')
    gflag: bool = False
    interface.add_argument('-g', dest='gflag', action='store_true')
    commands = {'opt': SharedOpt}
    ALLOW_PARSE = True

class Outer(ApplicationGroup):
    interface = Interface('outer', 'usage: outer <command>', 'usage: outer <command>\n\nOUTER-HELP',
                          disable_colors=True)
    command: str = None
    interface.add_argument('command')
    commands = {'sub': AllowGroup, 'plain': Group, 'opt': AllowOptGroup}

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


def parse_error(app: str, argv: list) -> str:
    """The ArgumentError message `app.interface.parse_args(argv)` raises, from its own child."""
    proc = child(f'''
try:
    {app}.interface.parse_args({argv!r})
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
    # Review cycle 1, F1: setups that leave no handler at all on the propagate walk. Python's
    # last resort prints the record itself, bare; cmdkit must not print it a second time.
    no_handler = [
        ('dictConfig naming cmdkit strips its handlers',
         "import logging.config; logging.config.dictConfig({'version': 1, 'loggers': {'cmdkit': {'level': 'WARNING'}}})"),
        ("cmdkit's handlers cleared", "logging.getLogger('cmdkit').handlers.clear()"),
        ('cmdkit.app propagate False', "logging.getLogger('cmdkit.app').propagate = False"),
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
        for setup_name, setup in no_handler:
            proc = run_main(f'{app}.main({argv!r})', body_pre=setup)
            check(f'no handler at all, Python prints once: {setup_name}: {name}',
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

    # Review cycle 2, F3: cmdkit's own NullHandler is the one its __init__ marks. An application's
    # own NullHandler on the cmdkit logger is the application's: silent, as in Python and 2.7.7.
    proc = run_main("Group.main(['bogus'])", body_pre="logging.getLogger('cmdkit').addHandler(logging.NullHandler())")
    check("application NullHandler added on the cmdkit logger: cmdkit stays silent",
          proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    proc = run_main("Group.main(['bogus'])",
                    pre="import logging; logging.getLogger('cmdkit').addHandler(logging.NullHandler())")
    check("application NullHandler added on the cmdkit logger before cmdkit is imported: silent",
          proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    recipe = ("import logging.config; logging.config.dictConfig({'version': 1, "
              "'handlers': {'null': {'class': 'logging.NullHandler'}}, "
              "'loggers': {'cmdkit': {'handlers': ['null']%s}}})")
    for name, extra in (('propagate False', ", 'propagate': False"), ('propagate left True', '')):
        proc = run_main("Group.main(['bogus'])", pre=recipe % extra)
        check(f'dictConfig routes cmdkit to a NullHandler before cmdkit is imported, {name}: silent',
              proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
        proc = run_main("Group.main(['bogus'])", body_pre=recipe % extra)
        check(f'dictConfig routes cmdkit to a NullHandler, {name}: cmdkit stays silent',
              proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
        proc = run_main("Group.main(['cmd', 'x', '--bogus'])", body_pre=recipe % extra)
        check(f'dictConfig routes cmdkit to a NullHandler, {name}: silent for an error inside a command',
              proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre='import importlib, cmdkit; importlib.reload(cmdkit)')
    check("cmdkit reloaded (a second marked NullHandler): the bare line once",
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))

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
    # Review cycle 1, F3: a filter on cmdkit.app that rejects the record stops Python before it
    # looks for handlers, so nothing is printed; one that accepts it changes nothing. Python
    # consults only the logging logger's own filters, so a rejecting filter on cmdkit does not
    # silence the line.
    reject = 'class Reject(logging.Filter):\n    def filter(self, record):\n        return False\n'
    accept = 'class Accept(logging.Filter):\n    def filter(self, record):\n        return True\n'
    proc = run_main("Group.main(['bogus'])", body_pre=reject + "logging.getLogger('cmdkit.app').addFilter(Reject())")
    check('a filter on cmdkit.app rejects the record: cmdkit silent',
          proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    proc = run_main("Group.main(['cmd', 'x', '--bogus'])",
                    body_pre=reject + "logging.getLogger('cmdkit.app').addFilter(Reject())")
    check('a filter on cmdkit.app rejects the record: cmdkit silent, error inside a group command',
          proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre=accept + "logging.getLogger('cmdkit.app').addFilter(Accept())")
    check('a filter on cmdkit.app accepts the record: the bare line once',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))
    by_message = ('class ByMessage(logging.Filter):\n    def filter(self, record):\n'
                  "        return 'bogus' not in record.getMessage()\n")
    proc = run_main("Group.main(['bogus'])", body_pre=by_message + "logging.getLogger('cmdkit.app').addFilter(ByMessage())")
    check('a filter on cmdkit.app rejects the message: cmdkit silent',
          proc.returncode == 2 and proc.stdout == b'' and proc.stderr == b'', show(proc))
    by_level = ('class ByLevel(logging.Filter):\n    def filter(self, record):\n'
                '        return record.levelno >= logging.CRITICAL\n')
    proc = run_main("Group.main(['bogus'])", body_pre=by_level + "logging.getLogger('cmdkit.app').addFilter(ByLevel())")
    check('a filter on cmdkit.app passes CRITICAL only: the bare line once',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre="logging.getLogger('cmdkit.app').addFilter(logging.Filter('cmdkit.app'))")
    check('a name filter for cmdkit.app on cmdkit.app: the bare line once',
          proc.returncode == 2 and proc.stdout == b''
          and proc.stderr == b'unrecognized command: bogus\n', show(proc))
    proc = run_main("Group.main(['bogus'])", body_pre=reject + "logging.getLogger('cmdkit').addFilter(Reject())")
    check('a rejecting filter on the cmdkit logger, which Python does not consult: the bare line once',
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
    import cmdkit
    out['module'] = sorted(name for name in vars(cmdkit) if not name.startswith('__'))
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
              and before == after and before['stderr'] is True
              and not [name for name in before['module'] if name.startswith('_null')])
        detail = f'before={before} after={after}'
    except ValueError:
        ok, detail = False, show(proc)
    check('footprint: handlers after import and after a reported error are 2.7.7\'s', ok, detail)


def noargs() -> None:
    """A bare group exactly as in 2.7.7, apart from R1 (GOAL C9); a bare plain application."""
    usage = {'Group': b'usage: app <command>\n', 'OptGroup': b'usage: opt [<command>]\n'}
    helps = {'Group': b'usage: app <command>\n\nGROUP-HELP\n', 'OptGroup': b'usage: opt [<command>]\n\nOPT-HELP\n',
             'BoomGroup': b'usage: boom <command>\n\nBOOM-HELP\n'}
    cmd_usage = b'usage: app cmd ARG [-d]\n'

    def ok(name: str, proc: subprocess.CompletedProcess, status: int, out: bytes, err: bytes) -> None:
        check(name, proc.returncode == status and proc.stdout == out and proc.stderr == err, show(proc))

    def error(message) -> tuple:
        return (2, b'', (message + '\n').encode()) if message else (None, None, None)

    # main([]) never reads sys.argv: every main([]) case runs with junk there (adversarial review).
    junk = "sys.argv = ['app', 'bogus', 'x']"

    # Without ALLOW_NOARGS (or with a value that is not True): every bare run prints the usage and
    # returns 1, whatever sys.argv holds.
    for group, base in (('Group', 'Group'), ('OptGroup', 'OptGroup'), ('TruthyGroup', 'Group')):
        ok(f'{group}.main([]): usage, 1', run_main(f'{group}.main([])', body_pre=junk), 1, usage[base], b'')
        for argv in ([], ['bogus'], ['--help'], ['--version'], ['cmd', 'x']):
            ok(f'{group}.main(None), sys.argv {argv}: usage, 1',
               run_main(f'{group}.main(None)', body_pre=f'sys.argv = {["app"] + argv!r}'), 1, usage[base], b'')
    ok("Outer.main(['plain']): the bare sub-group's usage, 1", run_main("Outer.main(['plain'])"), 1, usage['Group'], b'')

    # With ALLOW_NOARGS: the command line is parsed ([] as given, None from sys.argv) and handled as
    # 2.7.7 handles it. A group that requires its command reports it missing (R1), never its help.
    required = [('AllowGroup', 'Group'), ('AllowParseGroup', 'Group'), ('BoomGroup', 'BoomGroup')]
    optional = [('AllowOptGroup', 'OptGroup')]
    for group, base in required + optional:
        is_optional = (group, base) in optional
        bare = (0, b'default action\n', b'') if is_optional else error(parse_error(group, []))
        for call, body in (('main([])', junk), ('main()', "sys.argv = ['app']"),
                           ('main(None)', "sys.argv = ['app']")):
            ok(f'{group}.{call}, bare: as 2.7.7 ({"run" if is_optional else "the missing command reported"})',
               run_main(f'{group}.{call}', body_pre=body), *bare)
        cases = [
            (['bogus'], error('unrecognized command: bogus')),
            (['--help'], (0, helps[base], b'')),
            (['cmd', 'x'], error(parse_error(group, ['cmd', 'x']))),
            (['--bogus'], error(parse_error(group, ['--bogus']))),
            (['cmd'], (1, cmd_usage, b'')),
        ]
        if base != 'BoomGroup':
            cases.append((['--version'], (0, b'9.9.9\n', b'')))
        else:
            cases.append((['--boom'], (7, b'', b'')))
        for argv, expected in cases:
            ok(f'{group}.main(None), sys.argv {argv}: as 2.7.7',
               run_main(f'{group}.main(None)', body_pre=f'sys.argv = {["app"] + argv!r}'), *expected)
    ok("Outer.main(['sub']): the bare required sub-group reports the missing command once, 2",
       run_main("Outer.main(['sub'])", body_pre=junk), *error(parse_error('AllowGroup', [])))
    ok("Outer.main(['opt']): the bare optional sub-group runs, 0",
       run_main("Outer.main(['opt'])", body_pre=junk), 0, b'default action\n', b'')
    ok("ParseOuter.main(['-g', 'opt']): the bare sub-group gets the parent's shared options",
       run_main("ParseOuter.main(['-g', 'opt'])", body_pre=junk), 0, b"shared {'gflag': True}\n", b'')
    ok("AllowOptGroup.main(['cmd', 'x']): a named command runs", run_main("AllowOptGroup.main(['cmd', 'x'])"),
       0, b'ran cmd x\n', b'')
    proc = child("sys.exit(0 if 'main' not in vars(ApplicationGroup) else 1)")
    check('ApplicationGroup defines no main of its own, as in 2.7.7', proc.returncode == 0, show(proc))

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
