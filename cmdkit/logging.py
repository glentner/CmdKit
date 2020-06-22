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
Logging for cmdkit.

Add :class:`~logalpha.handlers.Handler` instances to the `cmdkit.logging.log`
instance to pick up messages from :mod:`cmdkit` events (e.g., argument errors).

Or, inject a custom logger by assigning it back to the module.
Be sure to include the logger used in the `Application` class.

Example:
    >>> from cmdkit import logging as _cmdkit_logging
    >>> from cmdkit.app import Application
    >>> _cmdkit_logging.log = log
    >>> Application.log_error = log.critical
"""

# standard libs
import io
import sys
from dataclasses import dataclass

# external libs
from logalpha.colors import Color
from logalpha.levels import Level, LEVELS
from logalpha.loggers import Logger
from logalpha.handlers import Handler
from logalpha.messages import Message


@dataclass
class ConsoleHandler(Handler):
    """Colorized handler writes to <stderr>."""

    level: Level = LEVELS[2]  # Level(value=2, name='WARNING')
    resource: io.TextIOWrapper = sys.stderr

    def format(self, msg: Message) -> str:
        return (f'{Logger.colors[msg.level.value].foreground}'
                f'{msg.level.name}{Color.reset} '
                f'{msg.content}')


# add handlers to pick up messages
log = Logger()
log.handlers.append(ConsoleHandler())
