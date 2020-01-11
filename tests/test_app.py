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


# external libs
import pytest

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
        DemoApp.from_cmdline([]) # missing `arg_1`


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
