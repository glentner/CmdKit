# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Implements the `Interface` class.

This module provides a modification to the standard `argparse.ArgumentParser`.
Instead of allowing it to construct usage and help statements, the `Interface`
class takes a pre-constructed usage and help string and uses those instead.
Further, it suppresses the exit behavior and always raises an `ArgumentError`
instead of trying to exit the program immediately.
"""


# type annotations
from __future__ import annotations
from typing import Callable

# standard libs
import argparse as _argparse

# internal libs
from cmdkit.ansi import colorize_usage

# public interface
__all__ = ['Interface', 'ArgumentError', 'HelpOption', 'VersionOption']

# elevate to this module
Namespace = _argparse.Namespace


class HelpOption(Exception):
    """Raised by :class:`~Interface` when the help option is passed."""


class VersionOption(Exception):
    """Raised by :class:`~Interface` whenever ``action='version'``."""


class ArgumentError(Exception):
    """Raised by :class:`~Interface` on bad arguments."""


# override version action to raise instead
def _version_action(self, parser, namespace, values, option_string=None) -> None:  # noqa: unused args
    raise VersionOption(self.version if self.version is not None else parser.version)
_argparse._VersionAction.__call__ = _version_action   # noqa: (protected)


class Interface(_argparse.ArgumentParser):
    """
    Variant of :class:`argparse.ArgumentParser` that raises an :class:`ArgumentError`
    instead of calling :meth:`sys.exit`. See the standard library documentation for
    details on :meth:`~Interface.add_argument` and other common methods.

    The `usage_text` and `help_text` are taken verbatim; however, these text values
    can be colorized automatically using a generalized syntax highlighter
    (:meth:`cmdkit.ansi.colorize_usage` by default).
    To disable this behavior, use the `disable_colors` parameter.
    """

    def __init__(self,
                 program: str,
                 usage_text: str,
                 help_text: str,
                 disable_colors: bool = False,
                 formatter: Callable[[str], str] = colorize_usage,
                 **kwargs) -> None:
        """Initialize with text and formatting arguments."""
        self.program = program
        if disable_colors:
            self.usage_text = usage_text
            self.help_text = help_text
        else:
            self.usage_text = formatter(usage_text)
            self.help_text = formatter(help_text)
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
