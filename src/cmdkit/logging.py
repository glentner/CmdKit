# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Expanded logging interface built on top of the standard `logging` module."""


# type annotations
from __future__ import annotations
from typing import Dict, Tuple, Type

# standard libraries
import uuid
import socket
import datetime
import logging

# internal libs
from cmdkit.ansi import Ansi, COLOR_STDERR

# public interface
__all__ = ['Logger', 'HOSTNAME', 'INSTANCE',
           'level_color', 'level_by_name',
           'logging_styles', 'DEFAULT_LOGGING_STYLE',
           'NOTSET', 'DEVEL', 'TRACE', 'DEBUG', 'INFO', 'NOTICE', 'WARNING', 'ERROR', 'CRITICAL']


# Cached for later use
HOSTNAME = socket.gethostname()
HOSTNAME_SHORT = HOSTNAME.split('.', 1)[0]


# Unique for every instance of the program
INSTANCE = str(uuid.uuid4())


# Canonical colors for logging messages
level_color: Dict[str, Ansi] = {
    'NULL': Ansi.NULL,
    'DEVEL': Ansi.RED,
    'TRACE': Ansi.CYAN,
    'DEBUG': Ansi.BLUE,
    'INFO': Ansi.GREEN,
    'NOTICE': Ansi.CYAN,
    'WARNING': Ansi.YELLOW,
    'ERROR': Ansi.RED,
    'CRITICAL': Ansi.MAGENTA
}


NOTICE: int = logging.INFO + 5
logging.addLevelName(NOTICE, 'NOTICE')


TRACE: int = logging.DEBUG - 5
logging.addLevelName(TRACE, 'TRACE')


DEVEL: int = 1
logging.addLevelName(DEVEL, 'DEVEL')


# Re-export for convenience
NOTSET: int = logging.NOTSET
DEBUG: int = logging.DEBUG
INFO: int = logging.INFO
WARNING: int = logging.WARNING
ERROR: int = logging.ERROR
CRITICAL: int = logging.CRITICAL


level_by_name: Dict[str, int] = {
    'NOTSET': logging.NOTSET,
    'DEVEL': DEVEL,
    'TRACE': TRACE,
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'NOTICE': NOTICE,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


DEFAULT_LOGGING_STYLE = 'default'
logging_styles = {
    'default': {
        'format': ('%(ansi_bold)s%(ansi_level)s%(levelname)8s%(ansi_reset)s %(ansi_faint)s[%(name)s]%(ansi_reset)s'
                   ' %(message)s'),
    },
    'system': {
        'format': '%(asctime)s.%(msecs)03d %(hostname)s %(levelname)8s [%(app_id)s] [%(name)s] %(message)s',
    },
    'detailed': {
        'format': ('%(ansi_faint)s%(asctime)s.%(msecs)03d %(hostname)s %(ansi_reset)s'
                   '%(ansi_level)s%(ansi_bold)s%(levelname)8s%(ansi_reset)s '
                   '%(ansi_faint)s[%(name)s]%(ansi_reset)s %(message)s'),
    },
    'detailed-compact': {
        'format': ('%(ansi_faint)s%(elapsed_hms)s [%(hostname_short)s] %(ansi_reset)s'
                   '%(ansi_level)s%(ansi_bold)s%(levelname)8s%(ansi_reset)s '
                   '%(ansi_faint)s[%(relative_name)s]%(ansi_reset)s %(message)s'),
    },
    'short': {
        'format': '[%(ansi_level)s%(levelname)s%(ansi_reset)s] %(message)s',
    }
}


class Logger(logging.Logger):
    """Extend standard `logging.Logger` with NOTICE, TRACE, and DEVEL levels."""

    def notice(self, msg: str, *args, **kwargs):
        """Log 'msg % args' with severity 'NOTICE'."""
        if self.isEnabledFor(NOTICE):
            self._log(NOTICE, msg, args, **kwargs)

    def trace(self, msg: str, *args, **kwargs):
        """Log 'msg % args' with severity 'TRACE'."""
        if self.isEnabledFor(TRACE):
            self._log(TRACE, msg, args, **kwargs)

    def devel(self, msg: str, *args, **kwargs):
        """Log 'msg % args' with severity 'DEVEL'."""
        if self.isEnabledFor(DEVEL):
            self._log(DEVEL, msg, args, **kwargs)

    @classmethod
    def with_name(cls: Type[Logger], name: str) -> Logger:
        """Shorthand for `log: Logger = logging.getLogger(name)`."""
        return logging.getLogger(name)

    @classmethod
    def default(cls: Type[Logger],
                name: str = '',
                format: str = logging_styles['default']['format'],
                **kwargs) -> Logger:
        """Calls standard `logging.basicConfig` and returns logger."""
        logging.basicConfig(format=format, **kwargs)
        return cls.with_name(name)


# Register new Logger implementation
logging.setLoggerClass(Logger)


def solve_relative_time(elapsed: float) -> Tuple[float, int, datetime.timedelta, str]:
    """
    Multiple formats of relative time since `elapsed` seconds.
    Returns:
        - Relative time in seconds (i.e., `elapsed`)
        - Relative time in milliseconds
        - Relative time as `datetime.timedelta`
        - Relative time in dd-hh:mm:ss.sss format
    """
    elapsed_ms = int(elapsed * 1000)
    reltime_delta = datetime.timedelta(seconds=elapsed)
    reltime_delta_hours, remainder = divmod(reltime_delta.seconds, 3600)
    reltime_delta_minutes, reltime_delta_seconds = divmod(remainder, 60)
    reltime_delta_milliseconds = int(reltime_delta.microseconds / 1000)
    return (
        elapsed,
        elapsed_ms,
        reltime_delta,
        f'{reltime_delta.days:02d}-{reltime_delta_hours:02d}:{reltime_delta_minutes:02d}:'
        f'{reltime_delta_seconds:02d}.{reltime_delta_milliseconds:03d}'
    )


class LogRecord(logging.LogRecord):
    """Extends standard `logging.LogRecord` to include ANSI colors, time formats, and other attributes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Context attributes
        self.app_id = INSTANCE
        self.hostname = HOSTNAME
        self.hostname_short = HOSTNAME_SHORT

        # Guard against `logging.makeLogRecord` passing None (see Issue #20)
        if isinstance(self.name, str):
            self.relative_name = self.name.split('.', 1)[-1]
        else:
            self.relative_name = None

        # Formatting attributes
        self.ansi_level = level_color.get(self.levelname, Ansi.NULL).value if COLOR_STDERR else ''
        self.ansi_reset = Ansi.RESET.value if COLOR_STDERR else ''
        self.ansi_bold = Ansi.BOLD.value if COLOR_STDERR else ''
        self.ansi_faint = Ansi.FAINT.value if COLOR_STDERR else ''
        self.ansi_italic = Ansi.ITALIC.value if COLOR_STDERR else ''
        self.ansi_underline = Ansi.UNDERLINE.value if COLOR_STDERR else ''
        self.ansi_black = Ansi.BLACK.value if COLOR_STDERR else ''
        self.ansi_red = Ansi.RED.value if COLOR_STDERR else ''
        self.ansi_green = Ansi.GREEN.value if COLOR_STDERR else ''
        self.ansi_yellow = Ansi.YELLOW.value if COLOR_STDERR else ''
        self.ansi_blue = Ansi.BLUE.value if COLOR_STDERR else ''
        self.ansi_magenta = Ansi.MAGENTA.value if COLOR_STDERR else ''
        self.ansi_cyan = Ansi.CYAN.value if COLOR_STDERR else ''
        self.ansi_white = Ansi.WHITE.value if COLOR_STDERR else ''

        # Timing attributes
        (self.elapsed,
         self.elapsed_ms,
         self.elapsed_delta,
         self.elapsed_hms) = solve_relative_time(self.relativeCreated / 1000)


# Register new LogRecord implementation
logging.setLogRecordFactory(LogRecord)
