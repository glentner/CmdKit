# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for `cmdkit.app` behavior and interfaces."""


# type annotations
from typing import Iterator, List, Type

# standard libs
import io
import os
import sys
import logging
import importlib
import subprocess
from contextlib import contextmanager, redirect_stderr
from string import ascii_letters

# external libs
import pytest
from hypothesis import given, strategies

# internal libs
import cmdkit
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError
from cmdkit.namespace import Namespace

DEMO_NAME = 'demo_app'
DEMO_DESCRIPTION = """\
Demonstration program for unit testing purposes.
"""

DEMO_USAGE = f"""\
usage: demo_app <arg_1> [-o | --option VALUE] [-d | --debug]
                [-h | --help]

{DEMO_DESCRIPTION}
"""

DEMO_HELP = f"""\
{DEMO_USAGE}

options:
<arg_1>               First input argument.

-o, --option VALUE    Some option with a value.
-d, --debug           Turn on debugging messages.
-h, --help            Show this message and exit.
"""


class DemoApp(Application):
    """Fixture for Application class to run unit tests against."""

    interface = Interface(DEMO_NAME, DEMO_USAGE, DEMO_HELP)

    arg_1: str = None
    interface.add_argument('arg_1')

    option_1: int = 4  # arbitrary
    interface.add_argument('-o', '--option', dest='option_1', type=int, default=option_1)

    debug_mode: bool = False
    interface.add_argument('-d', '--debug', dest='debug_mode', action='store_true')

    def run(self) -> None:
        """Business logic of application."""
        pass


class FileApp(DemoApp):
    """DemoApp opens a non-existent file."""
    def run(self) -> None:
        with open('NONEXISTENT-FILE', mode='r'):
            pass


class FileAppWithExceptionHandling(FileApp):
    """FileApp catches FileNotFoundError."""
    exceptions = {FileNotFoundError: (lambda exc: 1)}


def test_app_noargs(capsys) -> None:
    """Initialize and run the application."""
    with pytest.raises(ArgumentError):
        with DemoApp.from_cmdline([]):
            pass


@given(strategies.text(ascii_letters, min_size=1))
def test_app_arg_1(value) -> None:
    """The positional argument is captured."""
    with DemoApp.from_cmdline([value]) as app:
        assert app.arg_1 == value


def test_app_option_1_default() -> None:
    """The optional argument has a default value."""
    with DemoApp.from_cmdline(['arg_1']) as app:
        assert app.option_1 == DemoApp.option_1


@given(strategies.integers())
def test_app_option_1_given(value) -> None:
    """The optional argument was given."""
    with DemoApp.from_cmdline(['arg_1', '--option', str(value)]) as app:
        assert app.option_1 == value
    with DemoApp.from_cmdline(['arg_1', '-o', str(value)]) as app:
        assert app.option_1 == value


@given(strategies.text(ascii_letters, min_size=1, max_size=2))
def test_app_option_1_is_integer(value) -> None:
    """The optional argument was given a non-integer value."""
    with pytest.raises(ArgumentError):
        with DemoApp.from_cmdline(['arg_1', '--option', str(value)]):
            pass
    with pytest.raises(ArgumentError):
        with DemoApp.from_cmdline(['arg_1', '-o', str(value)]):
            pass


def test_app_debug_mode_not_given() -> None:
    """The debug mode flag was not given."""
    with DemoApp.from_cmdline(['arg_1']) as app:
        assert app.debug_mode is False


def test_app_debug_mode_given() -> None:
    """The debug mode flag was not given."""
    with DemoApp.from_cmdline(['arg_1', '--debug']) as app:
        assert app.debug_mode is True
    with DemoApp.from_cmdline(['arg_1', '-d']) as app:
        assert app.debug_mode is True


def test_app_usage(capsys) -> None:
    """Usage statement printed to <stdout> on no arguments."""
    status = DemoApp.main([])
    captured = capsys.readouterr()
    assert captured.out.strip() == DEMO_USAGE.strip()
    assert status == exit_status.usage


class NoargsDemoApp(DemoApp):
    """DemoApp runs with no arguments, but still requires its positional argument."""
    ALLOW_NOARGS = True


def test_app_noargs_allowed_missing_positional(capsys) -> None:
    """With ALLOW_NOARGS, a missing positional is an argument error written to <stderr>."""
    message = argument_error(DemoApp, [])
    assert 'arg_1' in message
    with no_logging_configured():
        status = NoargsDemoApp.main([])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == message + '\n'


class NoargsApp(Application):
    """Application with no required arguments that runs with none."""

    interface = Interface('noargs_app', 'usage: noargs_app [-d]', 'usage: noargs_app [-d]\n\nNo arguments.')
    ALLOW_NOARGS = True

    debug_mode: bool = False
    interface.add_argument('-d', '--debug', dest='debug_mode', action='store_true')

    def run(self) -> None:
        print(f'debug: {self.debug_mode}')


def test_app_noargs_allowed_runs(capsys) -> None:
    """With ALLOW_NOARGS and no required arguments, the application runs."""
    status = NoargsApp.main([])
    captured = capsys.readouterr()
    assert captured.out == 'debug: False\n'
    assert captured.err == ''
    assert status == exit_status.success


def test_app_help_1(capsys) -> None:
    """Help statement printed to <stdout> with `-h`."""
    status = DemoApp.main(['-h'])
    captured = capsys.readouterr()
    assert captured.out.strip() == DEMO_HELP.strip()
    assert status == exit_status.success


def test_app_help_2(capsys) -> None:
    """Help statement printed to <stdout> with `--help`."""
    status = DemoApp.main(['--help'])
    captured = capsys.readouterr()
    assert captured.out.strip() == DEMO_HELP.strip()
    assert status == exit_status.success


@given(strategies.integers(min_value=2, max_value=10))
def test_app_invalid_number_of_positional(count) -> None:
    """Too many positional arguments are given."""
    with pytest.raises(ArgumentError):
        with DemoApp.from_cmdline(['arg']*count):
            pass


@given(strategies.text(ascii_letters, min_size=2, max_size=10))
def test_app_invalid_options(opt):
    """An invalid option is given."""
    if opt not in ('debug', 'option'):
        with pytest.raises(ArgumentError):
            with DemoApp.from_cmdline(['arg_1', f'--{opt}']):
                pass


def test_app_exceptions() -> None:
    """Test exception handling."""
    with pytest.raises(FileNotFoundError):
        FileApp.main(['-'])
    status = FileAppWithExceptionHandling.main(['-'])
    assert status == 1


CMD1 = 'aaaa'
CMD1_USAGE = """\
usage: app aaaa [-h] ARG [-d] [-o VALUE]
Subcommand one.
"""
CMD1_HELP = """\
{CMD1_USAGE}
options:
ARG                   Some positional argument.

-o, --option VALUE    Some option with a value.
-d, --debug           Turn on debugging messages.
-h, --help            Show this message and exit.
"""


class Command1(Application):

    interface = Interface(CMD1, CMD1_USAGE, CMD1_HELP)

    arg: str = None
    interface.add_argument('arg')

    option: int = 42  # arbitrary
    interface.add_argument('-o', '--option', type=int, default=option)

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    def run(self) -> None:
        print(f'arg: {self.arg}, option: {self.option}, debug: {self.debug}')


CMD2 = 'bbbb'
CMD2_USAGE = """\
usage: app bbbb [-h] ARG [-d] [-o VALUE]
Subcommand two.
"""
CMD2_HELP = """\
{CMD2_USAGE}
options:
ARG                   Some positional argument.

-o, --option VALUE    Some option with a value.
-d, --debug           Turn on debugging messages.
-h, --help            Show this message and exit.
"""


class Command2(Application):

    interface = Interface(CMD2, CMD2_USAGE, CMD2_HELP)

    arg: str = None
    interface.add_argument('arg')

    option: int = 42  # arbitrary
    interface.add_argument('-o', '--option', type=int, default=option)

    debug: bool = False
    interface.add_argument('-d', '--debug', action='store_true')

    def run(self) -> None:
        print(f'arg: {self.arg}, option: {self.option}, debug: {self.debug}')


APP = 'app'
APP_USAGE = """\
usage: app [-h] <command> [<options>...]
Some application.
"""
APP_HELP = """\
{CMD2_USAGE}
commands:
aaaa                  Subcommand one.
bbbb                  Subcommand two.

options:
-g, --global          Global option.
-v, --version         Show version number and exit.
-h, --help            Show this message and exit.
"""


class Group(ApplicationGroup):

    interface = Interface(APP, APP_USAGE, APP_HELP)
    commands = {CMD1: Command1, CMD2: Command2}

    command: str = None
    interface.add_argument('command')

    version: str = '1.2.3'
    interface.add_argument('-v', '--version', action='version', version=version)


def test_app_group_noargs() -> None:
    """Initialize and run the application."""
    with pytest.raises(ArgumentError):
        Group.from_cmdline([])


def test_app_group_usage(capsys) -> None:
    """Usage statement printed to <stdout> on no arguments."""
    status = Group.main([])
    captured = capsys.readouterr()
    assert captured.out.strip() == APP_USAGE.strip()
    assert status == exit_status.usage


class NoargsGroup(Group):
    """Group that requires its command, with ALLOW_NOARGS set."""
    ALLOW_NOARGS = True


@pytest.mark.parametrize('cmdline', [[], None], ids=['empty', 'none'])
def test_app_group_noargs_allowed_missing_command(capsys, monkeypatch, cmdline) -> None:
    """With ALLOW_NOARGS, a group that requires its command reports it missing on <stderr>."""
    monkeypatch.setattr(sys, 'argv', [APP, ])
    message = argument_error(NoargsGroup, [])
    assert 'command' in message
    with no_logging_configured():
        status = NoargsGroup.main(cmdline)
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == message + '\n'


def test_app_group_usage_none(capsys, monkeypatch) -> None:
    """Usage statement printed to <stdout> when the command line is None."""
    monkeypatch.setattr(sys, 'argv', [APP, ])
    status = Group.main(None)
    captured = capsys.readouterr()
    assert captured.out.strip() == APP_USAGE.strip()
    assert captured.err == ''
    assert status == exit_status.usage


def test_app_group_noargs_allowed_reads_argv(capsys, monkeypatch) -> None:
    """With ALLOW_NOARGS, a command line of None reads <sys.argv>, and its errors are reported."""
    monkeypatch.setattr(sys, 'argv', [APP, 'bogus'])
    with no_logging_configured():
        status = NoargsGroup.main(None)
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == 'unrecognized command: bogus\n'


class OptionalGroup(ApplicationGroup):
    """Group whose command is optional, with a default action of its own."""

    interface = Interface(APP, APP_USAGE, APP_HELP)
    commands = {CMD1: Command1, CMD2: Command2}

    command: str = None
    interface.add_argument('command', nargs='?', default=None)

    def run(self) -> None:
        """Run the default action without a command, else delegate."""
        if self.command is None:
            print('default action')
        else:
            super().run()


class NoargsOptionalGroup(OptionalGroup):
    """Group with an optional command runs with no arguments."""
    ALLOW_NOARGS = True


def test_app_group_optional_command_usage(capsys) -> None:
    """Without ALLOW_NOARGS, a group with an optional command prints usage on no arguments."""
    status = OptionalGroup.main([])
    captured = capsys.readouterr()
    assert captured.out.strip() == APP_USAGE.strip()
    assert captured.err == ''
    assert status == exit_status.usage


@pytest.mark.parametrize('cmdline', [[], None], ids=['empty', 'none'])
def test_app_group_optional_command_noargs_allowed(capsys, monkeypatch, cmdline) -> None:
    """With ALLOW_NOARGS, a group with an optional command runs on no arguments."""
    monkeypatch.setattr(sys, 'argv', [APP, ])
    status = NoargsOptionalGroup.main(cmdline)
    captured = capsys.readouterr()
    assert captured.out == 'default action\n'
    assert captured.err == ''
    assert status == exit_status.success


def test_app_group_optional_command_given(capsys) -> None:
    """With ALLOW_NOARGS, a group with an optional command still runs a named command."""
    status = NoargsOptionalGroup.main([CMD1, 'foo'])
    captured = capsys.readouterr()
    assert captured.out == 'arg: foo, option: 42, debug: False\n'
    assert status == exit_status.success


def test_app_group_help_1(capsys) -> None:
    """Help statement printed to <stdout> with `-h`."""
    status = Group.main(['-h'])
    captured = capsys.readouterr()
    assert captured.out.strip() == APP_HELP.strip()
    assert status == exit_status.success


def test_app_group_help_2(capsys) -> None:
    """Help statement printed to <stdout> with `--help`."""
    status = Group.main(['--help'])
    captured = capsys.readouterr()
    assert captured.out.strip() == APP_HELP.strip()
    assert status == exit_status.success


def test_app_group_version_1(capsys) -> None:
    """Version number printed to <stdout> with `-v`."""
    status = Group.main(['-v'])
    captured = capsys.readouterr()
    assert captured.out.strip() == Group.version
    assert status == exit_status.success


def test_app_group_version_2(capsys) -> None:
    """Version number printed to <stdout> with `--version`."""
    status = Group.main(['--version'])
    captured = capsys.readouterr()
    assert captured.out.strip() == Group.version
    assert status == exit_status.success


def test_app_group_cmd1_usage(capsys) -> None:
    """Usage statement printed to <stdout> on no arguments."""
    status = Group.main([CMD1])
    captured = capsys.readouterr()
    assert captured.out.strip() == CMD1_USAGE.strip()
    assert status == exit_status.usage


def test_app_group_cmd1_help_1(capsys) -> None:
    """Help statement printed to <stdout> with `-h`."""
    status = Group.main([CMD1, '-h'])
    captured = capsys.readouterr()
    assert captured.out.strip() == CMD1_HELP.strip()
    assert status == exit_status.success


def test_app_group_cmd1_help_2(capsys) -> None:
    """Help statement printed to <stdout> with `--help`."""
    status = Group.main([CMD1, '--help'])
    captured = capsys.readouterr()
    assert captured.out.strip() == CMD1_HELP.strip()
    assert status == exit_status.success


def test_app_group_cmd2_usage(capsys) -> None:
    """Usage statement printed to <stdout> on no arguments."""
    status = Group.main([CMD2])
    captured = capsys.readouterr()
    assert captured.out.strip() == CMD2_USAGE.strip()
    assert status == exit_status.usage


def test_app_group_cmd2_help_1(capsys) -> None:
    """Help statement printed to <stdout> with `-h`."""
    status = Group.main([CMD2, '-h'])
    captured = capsys.readouterr()
    assert captured.out.strip() == CMD2_HELP.strip()
    assert status == exit_status.success


def test_app_group_cmd2_help_2(capsys) -> None:
    """Help statement printed to <stdout> with `--help`."""
    status = Group.main([CMD2, '--help'])
    captured = capsys.readouterr()
    assert captured.out.strip() == CMD2_HELP.strip()
    assert status == exit_status.success


def test_shared_group_construction(capsys) -> None:
    app = Group.from_cmdline([CMD2, 'foo', '--debug'])
    assert isinstance(app, ApplicationGroup)
    assert app.command == CMD2
    assert app.shared is None
    assert app.cmdline == ['foo', '--debug']


class Command3(Command2):
    def run(self) -> None:
        print(f'arg: {self.arg}, option: {self.option}, debug: {self.debug}, shared: {self.shared.opt}')


class SharedGroup(ApplicationGroup):

    interface = Interface(APP, APP_USAGE, APP_HELP)
    commands = {CMD1: Command1, CMD2: Command3}
    ALLOW_PARSE = True

    command: str = None
    interface.add_argument('command')

    version: str = '1.2.3'
    interface.add_argument('-v', '--version', action='version', version=version)

    opt: bool = False
    interface.add_argument('-g', '--global', action='store_true', dest='opt')


def test_app_group_cmd3_global_and_local_opt(capsys) -> None:
    status = SharedGroup.main(['--global', CMD2, 'foo', '--debug'])
    captured = capsys.readouterr()
    assert captured.out.strip() == f'arg: foo, option: 42, debug: True, shared: True'
    assert status == exit_status.success


def test_shared_group_option(capsys) -> None:
    app = SharedGroup.from_cmdline([CMD2, 'foo', '--debug'])
    assert isinstance(app, ApplicationGroup)
    assert app.command == CMD2
    assert app.shared == Namespace({'opt': False})
    assert app.cmdline == ['foo', '--debug']


@contextmanager
def no_logging_configured() -> Iterator[None]:
    """Hide the root logger's handlers (pytest's own) in a test body, then restore them in place."""
    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers.clear()
    try:
        yield
    finally:
        root.handlers[:] = saved


def argument_error(app: Type[Application], cmdline: List[str]) -> str:
    """The message of the ArgumentError that `app` raises for `cmdline`, parsing or running."""
    with pytest.raises(ArgumentError) as info:
        app.from_cmdline(cmdline).run()
    return str(info.value)


ARGUMENT_ERRORS = [
    pytest.param(DemoApp, ['arg_1', '--bogus'], DemoApp, ['arg_1', '--bogus'], '--bogus', id='unknown-flag'),
    pytest.param(DemoApp, ['--debug'], DemoApp, ['--debug'], 'arg_1', id='missing-positional'),
    pytest.param(Group, ['bogus'], Group, ['bogus'], 'bogus', id='unknown-command'),
    pytest.param(Group, [CMD1, 'x', '--bogus'], Command1, ['x', '--bogus'], '--bogus', id='command-unknown-flag'),
    pytest.param(Group, [CMD1, '--debug'], Command1, ['--debug'], 'arg', id='command-missing-positional'),
]


@pytest.mark.parametrize('app, cmdline, source, source_cmdline, token', ARGUMENT_ERRORS)
def test_app_argument_error_reported_without_logging(capsys, app, cmdline, source, source_cmdline, token) -> None:
    """With no logging configured, an argument error is written to <stderr> once, as is."""
    message = argument_error(source, source_cmdline)
    assert token in message
    with no_logging_configured():
        status = app.main(cmdline)
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == message + '\n'


@pytest.mark.parametrize('app, cmdline, source, source_cmdline, token', ARGUMENT_ERRORS)
def test_app_argument_error_logged_with_logging(capsys, caplog, app, cmdline, source, source_cmdline, token) -> None:
    """With logging configured, the handlers get one critical record and nothing else is written."""
    message = argument_error(source, source_cmdline)
    assert token in message
    status = app.main(cmdline)
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == ''
    assert [(r.name, r.levelno, r.getMessage()) for r in caplog.records] == [
        ('cmdkit.app', logging.CRITICAL, message)
    ]


def test_app_argument_error_log_critical_replaced_on_class(capsys) -> None:
    """A log_critical replaced on the class is called once, and nothing is written."""
    calls = []

    class Recorded(Group):
        log_critical = staticmethod(calls.append)

    with no_logging_configured():
        status = Recorded.main(['bogus'])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert [str(error) for error in calls] == ['unrecognized command: bogus']
    assert captured.out == ''
    assert captured.err == ''


def test_app_argument_error_log_critical_replaced_on_application(capsys, monkeypatch) -> None:
    """A log_critical replaced on Application is called once, and nothing is written."""
    calls = []
    monkeypatch.setattr(Application, 'log_critical', calls.append)
    message = argument_error(Command1, ['x', '--bogus'])
    with no_logging_configured():
        status = Group.main([CMD1, 'x', '--bogus'])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert [str(error) for error in calls] == [message]
    assert captured.out == ''
    assert captured.err == ''


def test_app_argument_error_log_critical_replaced_by_another_logger(capsys, monkeypatch) -> None:
    """A log_critical replaced by another logger's method leaves only Python's own line."""
    monkeypatch.setattr(Application, 'log_critical', logging.getLogger('elsewhere').critical)
    with no_logging_configured():
        status = Group.main(['bogus'])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == 'unrecognized command: bogus\n'


class SubNullHandler(logging.NullHandler):
    """A NullHandler that is not the plain one cmdkit attaches to its logger."""


def add_handler(request, name: str, handler: logging.Handler) -> None:
    """Attach `handler` to the logger `name` for the rest of the test."""
    logger = logging.getLogger(name)
    logger.addHandler(handler)
    request.addfinalizer(lambda: logger.removeHandler(handler))


def add_filter(request, name: str, rule) -> None:
    """Attach the filter `rule` to the logger `name` for the rest of the test."""
    logger = logging.getLogger(name)
    logger.addFilter(rule)
    request.addfinalizer(lambda: logger.removeFilter(rule))


def set_level(request, name: str, level: int) -> None:
    """Set the level of the logger `name` for the rest of the test (clearing the level cache)."""
    logger = logging.getLogger(name)
    request.addfinalizer(lambda old=logger.level: logger.setLevel(old))
    logger.setLevel(level)


def set_last_resort_level(request, level: int) -> None:
    """Set the level of Python's last-resort handler for the rest of the test."""
    request.addfinalizer(lambda old=logging.lastResort.level: logging.lastResort.setLevel(old))
    logging.lastResort.setLevel(level)


def reimport_cmdkit(monkeypatch) -> None:
    """Import the package a second time, its logger's handlers restored after the test."""
    logger = logging.getLogger('cmdkit')
    monkeypatch.setattr(logger, 'handlers', list(logger.handlers))
    importlib.reload(cmdkit)


def above_critical_root_handler() -> logging.Handler:
    """A handler of the application's whose level no record reaches."""
    handler = logging.StreamHandler()
    handler.setLevel(logging.CRITICAL + 1)
    return handler


LOGGING_SETUPS = [
    # the message once on stderr: cmdkit's line, or Python's own where no handler is found at all
    pytest.param(lambda mp, rq: None, True, id='unconfigured'),
    pytest.param(lambda mp, rq: mp.setattr(logging.getLogger('cmdkit'), 'handlers', []), True,
                 id='cmdkit-handlers-emptied'),
    pytest.param(lambda mp, rq: mp.setattr(logging.getLogger('cmdkit.app'), 'propagate', False), True,
                 id='app-logger-propagate-false'),
    pytest.param(lambda mp, rq: (mp.setattr(logging.getLogger('cmdkit'), 'propagate', False),
                                 add_handler(rq, '', logging.NullHandler())), True,
                 id='cmdkit-propagate-false-root-handler'),
    pytest.param(lambda mp, rq: reimport_cmdkit(mp), True,
                 id='package-imported-again'),
    pytest.param(lambda mp, rq: add_filter(rq, 'cmdkit.app', lambda record: True), True,
                 id='accepting-filter'),
    pytest.param(lambda mp, rq: add_filter(rq, 'cmdkit.app', lambda record: record.levelno == logging.CRITICAL),
                 True, id='critical-only-filter'),
    pytest.param(lambda mp, rq: add_filter(rq, 'cmdkit.app', logging.Filter('cmdkit.app')), True,
                 id='name-filter'),
    pytest.param(lambda mp, rq: add_filter(rq, 'cmdkit', lambda record: False), True,
                 id='rejecting-filter-on-cmdkit-not-consulted'),
    pytest.param(lambda mp, rq: set_last_resort_level(rq, logging.CRITICAL), True,
                 id='last-resort-at-critical'),
    pytest.param(lambda mp, rq: (set_level(rq, 'cmdkit.app', logging.ERROR),
                                 set_last_resort_level(rq, logging.ERROR)), True,
                 id='app-logger-and-last-resort-at-error'),
    # nothing on stderr: the application silenced the record, or a handler of its own is found
    pytest.param(lambda mp, rq: add_filter(rq, 'cmdkit.app', lambda record: False), False,
                 id='rejecting-filter'),
    pytest.param(lambda mp, rq: add_filter(rq, 'cmdkit.app', lambda record: 'bogus' not in record.getMessage()),
                 False, id='message-filter'),
    pytest.param(lambda mp, rq: mp.setattr(logging.getLogger('cmdkit.app'), 'disabled', True), False,
                 id='app-logger-disabled'),
    pytest.param(lambda mp, rq: set_level(rq, 'cmdkit.app', logging.CRITICAL + 1), False,
                 id='app-logger-above-critical'),
    pytest.param(lambda mp, rq: mp.setattr(logging, 'lastResort', None), False,
                 id='no-last-resort'),
    pytest.param(lambda mp, rq: set_last_resort_level(rq, logging.CRITICAL + 1), False,
                 id='last-resort-above-critical'),
    pytest.param(lambda mp, rq: add_handler(rq, '', logging.NullHandler()), False,
                 id='null-handler-on-root'),
    pytest.param(lambda mp, rq: add_handler(rq, 'cmdkit.app', logging.NullHandler()), False,
                 id='null-handler-on-app-logger'),
    pytest.param(lambda mp, rq: add_handler(rq, 'cmdkit', SubNullHandler()), False,
                 id='null-handler-subclass-on-cmdkit'),
    pytest.param(lambda mp, rq: add_handler(rq, 'cmdkit', logging.NullHandler()), False,
                 id='application-null-handler-on-cmdkit'),
    pytest.param(lambda mp, rq: mp.setattr(logging.getLogger('cmdkit'), 'handlers',
                                           [logging.NullHandler(), *logging.getLogger('cmdkit').handlers]), False,
                 id='application-null-handler-before-cmdkits'),
    pytest.param(lambda mp, rq: (mp.setattr(logging.getLogger('cmdkit'), 'handlers', [logging.NullHandler()]),
                                 mp.setattr(logging.getLogger('cmdkit'), 'propagate', False)), False,
                 id='cmdkit-routed-to-application-null-handler'),
    pytest.param(lambda mp, rq: add_handler(rq, '', above_critical_root_handler()), False,
                 id='root-handler-above-critical'),
]


@pytest.mark.parametrize('setup, once', LOGGING_SETUPS)
def test_app_argument_error_last_resort_rule(capsys, monkeypatch, request, setup, once) -> None:
    """The message is written once where only cmdkit's NullHandler held the last resort back, else not."""
    with no_logging_configured():
        setup(monkeypatch, request)
        status = Group.main(['bogus'])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == ('unrecognized command: bogus\n' if once else '')


DICT_CONFIG_RECIPE = """
import logging.config
config = {
    'version': 1,
    'handlers': {'null': {'class': 'logging.NullHandler'}},
    'loggers': {'cmdkit': {'handlers': ['null'], 'propagate': False}},
}
if ORDER == 'before':
    logging.config.dictConfig(config)
from cmdkit.app import ApplicationGroup
from cmdkit.cli import Interface
if ORDER == 'after':
    logging.config.dictConfig(config)

class Group(ApplicationGroup):
    interface = Interface('app', 'usage: app <command>', 'usage: app <command>')
    command: str = None
    interface.add_argument('command')
    commands = {}

raise SystemExit(Group.main(['bogus']))
"""


@pytest.mark.parametrize('order', ['before', 'after'])
def test_app_argument_error_silent_under_dict_config_null_handler(order) -> None:
    """Routing cmdkit to a NullHandler of the application's with dictConfig keeps the message silent."""
    code = f'ORDER = {order!r}\n' + DICT_CONFIG_RECIPE
    proc = subprocess.run([sys.executable, '-I', '-c', code],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    assert proc.returncode == exit_status.bad_argument
    assert proc.stdout == b''
    assert proc.stderr == b''


DEAD_STDERR_CHILD = """
import sys
from cmdkit.app import ApplicationGroup
from cmdkit.cli import Interface

class Group(ApplicationGroup):
    interface = Interface('app', 'usage: app <command>', 'usage: app <command>')
    command: str = None
    interface.add_argument('command')
    commands = {}

status = Group.main(['bogus'])
sys.stdout.write(str(status))
sys.stdout.flush()
"""


def test_app_argument_error_dead_stderr_pipe() -> None:
    """With <stderr> a pipe nobody reads, the failed write is ignored and main still returns 2."""
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        proc = subprocess.run([sys.executable, '-I', '-c', DEAD_STDERR_CHILD],
                              stdout=subprocess.PIPE, stderr=write_end, timeout=60)
    finally:
        os.close(write_end)
    assert proc.stdout == str(exit_status.bad_argument).encode()


def test_app_argument_error_no_stderr(capsys) -> None:
    """With no <stderr> at all, the message is skipped, and nothing goes to <stdout>."""
    with no_logging_configured(), redirect_stderr(None):
        status = Group.main(['bogus'])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == ''


def test_app_argument_error_closed_stderr(capsys) -> None:
    """With <stderr> closed, the failed write is ignored and main still returns 2."""
    stream = io.StringIO()
    stream.close()
    with no_logging_configured(), redirect_stderr(stream):
        status = Group.main(['bogus'])
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''


def test_app_library_handler_on_cmdkit_logger(capsys) -> None:
    """The library's one NullHandler sits on the cmdkit logger and quiets every cmdkit.* logger."""
    assert [type(handler) for handler in logging.getLogger('cmdkit').handlers] == [logging.NullHandler]
    assert logging.getLogger('cmdkit.app').handlers == []
    with no_logging_configured():
        logging.getLogger('cmdkit.config').warning('a warning with no logging configured')
    captured = capsys.readouterr()
    assert captured.out == ''
    assert captured.err == ''


def test_app_argument_error_silent_when_logging_disabled(capsys) -> None:
    """With logging disabled at the critical level, nothing is written, as without the report."""
    with no_logging_configured():
        logging.disable(logging.CRITICAL)
        try:
            status = Group.main(['bogus'])
        finally:
            logging.disable(logging.NOTSET)
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.out == ''
    assert captured.err == ''


def test_app_argument_error_leaves_no_handler(capsys) -> None:
    """Reporting an argument error attaches no handler to any logger."""
    names = ('cmdkit', 'cmdkit.app', '')
    with no_logging_configured():
        before = {name: logging.getLogger(name).handlers[:] for name in names}
        status = Group.main(['bogus'])
        after = {name: logging.getLogger(name).handlers[:] for name in names}
    captured = capsys.readouterr()
    assert status == exit_status.bad_argument
    assert captured.err == 'unrecognized command: bogus\n'
    assert before == after
