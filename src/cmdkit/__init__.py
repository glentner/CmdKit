# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Package initialization for CmdKit."""


# standard libs
from logging import NullHandler
from importlib.metadata import version as get_version

# internal libs
from cmdkit.cli import Interface, ArgumentError
from cmdkit.config import Configuration, ConfigurationError
from cmdkit.namespace import Namespace, Environ
from cmdkit.app import Application, ApplicationGroup, exit_status
from cmdkit.platform import AppContext
from cmdkit.logging import Logger, logging_styles, DEFAULT_LOGGING_STYLE

# public interface
__all__ = [
    'Interface', 'ArgumentError',
    'Configuration', 'ConfigurationError',
    'Namespace', 'Environ',
    'Application', 'ApplicationGroup', 'exit_status',
    'AppContext',
    'Logger', 'logging_styles', 'DEFAULT_LOGGING_STYLE'
]

# package metadata
__version__ = get_version('cmdkit')

# null-handler for library interface
Logger.with_name(__name__).addHandler(NullHandler())
