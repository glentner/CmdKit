# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Unit tests for `cmdkit.app` behavior and interfaces."""


# standard libs
from string import ascii_letters

# external libs
import pytest
from hypothesis import given, strategies

# internal libs
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.cli import Interface, ArgumentError
from cmdkit.config import Namespace


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
