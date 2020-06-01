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
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface, ArgumentError


DEMO_NAME = 'demo_app'
DEMO_DESCRIPTION = """\
Demonstation program for unit testing purposes.
"""

DEMO_USAGE = f"""\
usage: demo_app <arg_1> [-o | --option VALUE] [-d | --debug]
                [-h | --help]

{DEMO_DESCRIPTION}
"""

DEMO_HELP = f"""\
{DEMO_USAGE}

Options:
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


def test_app_noargs(capsys) -> None:
    """Initialize and run the application."""
    with pytest.raises(ArgumentError):
        with DemoApp.from_cmdline([]) as app:
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
        with DemoApp.from_cmdline(['arg_1', '--option', str(value)]) as app:
            pass
    with pytest.raises(ArgumentError):
        with DemoApp.from_cmdline(['arg_1', '-o', str(value)]) as app:
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
        with DemoApp.from_cmdline(['arg']*count) as app:
            pass


@given(strategies.text(ascii_letters, min_size=2, max_size=10))
def test_app_invalid_options(opt):
    """An invalid option is given."""
    if opt not in ('debug', 'option'):
        with pytest.raises(ArgumentError):
            with DemoApp.from_cmdline(['arg_1', f'--{opt}']) as app:
                pass