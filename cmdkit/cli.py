# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.


"""
Implements the `Interface` class.

This module provides a modification to the standard `argparse.ArgumentParser`.
Instead of allowing it to construct usage and help statements, the `Interface`
class takes a pre-constructed usage and help string and uses those instead.
Further, it suppresses the exit behavior and always raises an `ArgumentError`
instead of trying to exit the program immediately.
"""

# standard libs
import argparse as _argparse

# elevate to this module
Namespace = _argparse.Namespace


class HelpOption(Exception):
    """Raised when the `-h|--help` flag is given."""

class VersionOption(Exception):
    """Raised when the `--version` flag is given."""

class ArgumentError(Exception):
    """Exceptions originating from `argparse`."""


def _version_action(self, parser, namespace, values, option_string=None) -> None:
    raise VersionOption(self.version if self.version is not None else parser.version)


# override version action to raise exception
_argparse._VersionAction.__call__ = _version_action


class Interface(_argparse.ArgumentParser):
    """
    Variant of `argparse.ArgumentParser` that raises an ArgumentError instead of
    calling `sys.exit`. The `usage_text` and `help_text` will be taken verbatim.

    Example:
        >>> from cmdkit.cli import Interface
        >>> interface = Interface('my_app', 'usage: ...', 'help: ...')
        >>> interface.add_argument('--verbose', action='store_true')
    """

    def __init__(self, program: str, usage_text: str, help_text: str, **kwargs) -> None:
        """
        Explicitly provide `usage_text` and `help_text`.

        Arguments
        ---------
        program: str
            Name of program (e.g., `os.path.basename(sys.argv[0])`).

        usage_text: str
            Full text of program "usage" statement.

        help_text: str
            Full text of program "help" statement.

        See Also
        --------
        `argparse.ArgumentParser`
        """

        self.program = program
        self.usage_text = usage_text
        self.help_text = help_text
        super().__init__(prog=program, usage=usage_text, **kwargs)

    # prevents base class from trying to build up usage text
    def format_help(self) -> str:
        return self.help_text

    # prevents base class from trying to build up help text
    def format_usage(self) -> str:
        return self.usage_text

    # messages will be printed manually
    def print_usage(self, *args, **kwargs) -> None:
        return  # don't allow parser to print usage

    def print_help(self, *args, **kwargs) -> None:
        raise HelpOption(self.help_text)

    # don't allow base class attempt to exit
    def exit(self, status: int = 0, message: str = None) -> None:
        raise ArgumentError(message)

    # simple raise, no printing
    def error(self, message: str) -> None:
        raise ArgumentError(message)

