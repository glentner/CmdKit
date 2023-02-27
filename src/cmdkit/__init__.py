# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Package initialization for CmdKit."""


# standard libs
from logging import NullHandler

# internal libs
from .cli import Interface, ArgumentError
from .config import Namespace, Configuration, ConfigurationError
from .app import Application, ApplicationGroup, exit_status
from .platform import AppContext
from .logging import Logger, logging_styles, DEFAULT_LOGGING_STYLE

# public interface
__all__ = [
    'Interface', 'ArgumentError',
    'Namespace', 'Configuration', 'ConfigurationError',
    'Application', 'ApplicationGroup', 'exit_status',
    'AppContext',
    'Logger', 'logging_styles', 'DEFAULT_LOGGING_STYLE'
]

# package metadata
__version__   = '2.6.1'

# null-handler for library interface
Logger.with_name(__name__).addHandler(NullHandler())
