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
Application class implementation.
"""

# allow for return annotations
from __future__ import annotations

# standard libs
import abc
from typing import NamedTuple, List, Dict, Callable

# internal libs
from . import cli
from . import config
from .logging import log


class exit_status:
    """Collection of exit status values."""
    success:            int = 0
    usage:              int = 1
    bad_argument:       int = 2
    bad_config:         int = 3
    keyboard_interrupt: int = 4
    runtime_error:      int = 5
    uncaught_exception: int = 6


class Application(abc.ABC):
    """
    Abstract base class for all application interfaces.
    """

    interface: cli.Interface = None
    ALLOW_NOARGS: bool = False

    exceptions: Dict[Exception, Callable[[Exception], int]] = dict()
    log_error: Callable[[str], None] = log.critical  # pylint: disable=no-member


    def __init__(self, **parameters) -> None:
        """Direct initialization sets `parameters`."""
        for name, value in parameters.items():
            setattr(self, name, value)

    @classmethod
    def from_cmdline(cls, cmdline: List[str] = None) -> 'Application':
        """Initialize via command line arguments (e.g., `sys.argv`)."""
        return cls.from_namespace(cls.interface.parse_args(cmdline))

    @classmethod
    def from_namespace(cls, namespace: cli.Namespace) -> 'Application':
        """Initialize via existing namespace/namedtuple."""
        return cls(**vars(namespace))

    @classmethod
    def main(cls, cmdline: List[str] = None) -> int:
        """Entry-point for application."""

        try:
            if not cmdline:
                if hasattr(cls, 'ALLOW_NOARGS') and cls.ALLOW_NOARGS is True:
                    pass
                else:
                    print(cls.interface.usage_text)
                    return exit_status.usage

            with cls.from_cmdline(cmdline) as app:
                app.run()

            return exit_status.success

        except cli.HelpOption as help_text:
            print(help_text)
            return exit_status.success

        except cli.VersionOption as version:
            print(*version.args)
            return exit_status.success

        except cli.ArgumentError as error:
            cls.log_error(error)
            return exit_status.bad_argument

        except KeyboardInterrupt:
            cls.log_error('keyboard-interrupt: going down now!')
            return exit_status.keyboard_interrupt

        except Exception as error:
            for exc_type, exc_handler in cls.exceptions.items():
                if isinstance(error, exc_type):
                    return exc_handler(error)
            cls.log_error('uncaught exception occurred!')
            raise

    @abc.abstractmethod
    def run(self) -> None:
        """Business-logic of the application."""
        raise NotImplementedError()

    def __enter__(self) -> Application:
        """Place-holder for context manager."""
        return self
    
    def __exit__(self, *exc) -> None:
        """Release resources."""
        pass
