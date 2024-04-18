# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""ANSI color codes and methods."""


# type annotations
from __future__ import annotations
from typing import Callable

# standard libs
import os
import re
import sys
import functools
from enum import Enum

# public interface
__all__ = ['NO_COLOR', 'FORCE_COLOR', 'COLOR_STDOUT', 'COLOR_STDERR', 'Ansi', 'format_ansi',
           'bold', 'faint', 'italic', 'underline',
           'black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white',
           'colorize_usage', ]


# Enable/disable colors if necessary
NO_COLOR = False if not os.getenv('NO_COLOR') else True
FORCE_COLOR = False if not os.getenv('FORCE_COLOR') else True

COLOR_STDOUT = True
COLOR_STDERR = True
if not sys.stdout.isatty() or NO_COLOR:
    COLOR_STDOUT = False
if not sys.stderr.isatty() or NO_COLOR:
    COLOR_STDERR = False
if FORCE_COLOR:
    COLOR_STDOUT = True
    COLOR_STDERR = True


class Ansi(Enum):
    """Classic `ANSI` escape sequences for colors."""

    NULL = ''
    RESET = '\033[0m'
    BOLD = '\033[1m'
    FAINT = '\033[2m'
    ITALIC = '\033[3m'
    UNDERLINE = '\033[4m'
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'


def format_ansi(seq: Ansi, text: str) -> str:
    """
    Apply escape sequence with reset afterward, if necessary.
    If `stdout` is not a `TTY` or :data:`NO_COLOR` is set, there is no effect on `text`.
    If :data:`FORCE_COLOR` is set, formatting will be applied regardless.
    """
    if not COLOR_STDOUT:
        return text
    elif text.endswith(Ansi.RESET.value):
        return f'{seq.value}{text}'
    else:
        return f'{seq.value}{text}{Ansi.RESET.value}'


# shorthand formatting methods
bold = functools.partial(format_ansi, Ansi.BOLD)
faint = functools.partial(format_ansi, Ansi.FAINT)
italic = functools.partial(format_ansi, Ansi.ITALIC)
underline = functools.partial(format_ansi, Ansi.UNDERLINE)
black = functools.partial(format_ansi, Ansi.BLACK)
red = functools.partial(format_ansi, Ansi.RED)
green = functools.partial(format_ansi, Ansi.GREEN)
yellow = functools.partial(format_ansi, Ansi.YELLOW)
blue = functools.partial(format_ansi, Ansi.BLUE)
magenta = functools.partial(format_ansi, Ansi.MAGENTA)
cyan = functools.partial(format_ansi, Ansi.CYAN)
white = functools.partial(format_ansi, Ansi.WHITE)


def colorize_usage(text: str) -> str:
    """
    Apply rich :class:`Ansi` formatting to usage and help text.

    This function operates like a syntax highlighter for usage and help text.
    If `stdout` is not a `TTY` or :data:`NO_COLOR` is set, there is no effect on `text`.
    If :data:`FORCE_COLOR` is set, formatting will be applied regardless.
    """
    if not COLOR_STDOUT:  # NOTE: usage is on stdout not stderr
        return text
    else:
        return _apply_formatters(text,
                                 _format_headers,
                                 _format_options,
                                 _format_special_device,
                                 _format_special_metavars,
                                 _format_special_reserved_names,
                                 _format_single_quoted_string,
                                 _format_double_quoted_string,
                                 _format_backtick_string,
                                 _format_digit,
                                 )


def _apply_formatters(text: str, *formatters: Callable[[str], str]) -> str:
    """Apply all text `formatters`."""
    if formatters:
        return formatters[0](_apply_formatters(text, *formatters[1:]))
    else:
        return text


# Look-around pattern to negate matches within quotation marks
# Whole quotations are formatted together
NOT_QUOTED = (
    r'(?=([^"]*"[^"]*")*[^"]*$)' +
    r"(?=([^']*'[^']*')*[^']*$)" +
    r'(?=([^`]*`[^`]*`)*[^`]*$)'
)


def _format_headers(text: str) -> str:
    """Add rich ANSI formatting to section headers."""
    return re.sub(r'^(?P<name>[A-Z][a-z]+):' + NOT_QUOTED, bold(r'\g<name>:'),
                  text, flags=re.MULTILINE)


def _format_options(text: str) -> str:
    """Add rich ANSI formatting to option syntax."""
    option_pattern = r'(?P<leader>[ /\[,])(?P<option>-[a-zA-Z]+|--[a-z]+(-[a-z]+)?)\b'
    return re.sub(option_pattern + NOT_QUOTED, r'\g<leader>' + cyan(r'\g<option>'), text)


def _format_special_metavars(text: str) -> str:
    """Add rich ANSI formatting to special argument syntax."""
    metavars_pattern = r'(?<!-)\b(?P<arg>[A-Z]{2,})\b'
    return re.sub(metavars_pattern + NOT_QUOTED, italic(r'\g<arg>'), text)


def _format_special_device(text: str) -> str:
    """Add rich ANSI formatting to special device/resource names (e.g., '<stdout>')."""
    return re.sub(r'(?P<arg><[a-z]{3,}>)' + NOT_QUOTED, italic(r'\g<arg>'), text)


def _format_special_reserved_names(text: str) -> str:
    """Special reserved names (e.g., localhost)."""
    names = ['localhost', 'stdin', 'stdout', 'stderr', ]
    names_pattern = r'(?<!-)\b(?P<name>' + '|'.join(names) + r')\b'
    return re.sub(names_pattern + NOT_QUOTED, italic(r'\g<name>'), text)


def _format_single_quoted_string(text: str) -> str:
    """Add rich ANSI formatting to quoted strings."""
    return re.sub(r"'(?P<subtext>.*)'", yellow(r"'\g<subtext>'"), text)


def _format_double_quoted_string(text: str) -> str:
    """Add rich ANSI formatting to quoted strings."""
    return re.sub(r'"(?P<subtext>.*)"', yellow(r'"\g<subtext>"'), text)


def _format_backtick_string(text: str) -> str:
    """Add rich ANSI formatting to quoted strings."""
    return re.sub(r'`(?P<subtext>.*)`', yellow(r'`\g<subtext>`'), text)


def _format_digit(text: str) -> str:
    """Add rich ANSI formatting to numerical digits."""
    return re.sub(r'\b(?P<num>\d+\.?[kmgtKMGT]?[bB]?|null|NULL)\b' + NOT_QUOTED,
                  green(r'\g<num>'), text)
