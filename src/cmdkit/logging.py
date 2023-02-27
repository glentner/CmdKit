# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Expanded logging interface built on top of the standard `logging` module."""


# type annotations
from __future__ import annotations
from typing import Dict, Any, Type

# standard libraries
import uuid
import socket
import logging

# internal libs
from cmdkit.ansi import Ansi

# public interface
__all__ = ['Logger', 'HOSTNAME', 'INSTANCE',
           'level_color', 'level_by_name',
           'logging_styles', 'DEFAULT_LOGGING_STYLE', ]


# Cached for later use
HOSTNAME = socket.gethostname()


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
    def default(cls: Type[Logger], name: str, *args, **kwargs) -> Logger:
        """Calls standard `logging.basicConfig` and returns logger."""
        logging.basicConfig(*args, **kwargs)
        return cls.with_name(name)


# Register new Logger implementation
logging.setLoggerClass(Logger)


class LogRecord(logging.LogRecord):
    """Extends LogRecord to include the hostname, app_id, and ANSI color codes."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.app_id = INSTANCE
        self.hostname = HOSTNAME
        self.ansi_level = level_color.get(self.levelname, Ansi.NULL).value
        self.ansi_reset = Ansi.RESET.value
        self.ansi_bold = Ansi.BOLD.value
        self.ansi_faint = Ansi.FAINT.value
        self.ansi_italic = Ansi.ITALIC.value
        self.ansi_underline = Ansi.UNDERLINE.value
        self.ansi_black = Ansi.BLACK.value
        self.ansi_red = Ansi.RED.value
        self.ansi_green = Ansi.GREEN.value
        self.ansi_yellow = Ansi.YELLOW.value
        self.ansi_blue = Ansi.BLUE.value
        self.ansi_magenta = Ansi.MAGENTA.value
        self.ansi_cyan = Ansi.CYAN.value
        self.ansi_white = Ansi.WHITE.value


# Register new LogRecord implementation
logging.setLogRecordFactory(LogRecord)


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
    'short': {
        'format': '[%(ansi_level)s%(levelname)s%(ansi_reset)s] %(message)s',
    }
}
