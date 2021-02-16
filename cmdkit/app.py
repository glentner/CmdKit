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

# type annotations
from __future__ import annotations
from typing import List, Dict, Callable, NamedTuple, Type, TypeVar

# standard libs
import abc
import logging

# internal libs
from . import cli
from .config import Namespace


TApp = TypeVar('TApp', bound='Application')
TAppGrp = TypeVar('TAppGrp', bound='ApplicationGroup')


log = logging.getLogger(__name__)


class ExitStatus(NamedTuple):
    """Collection of exit status values."""
    success:            int = 0
    usage:              int = 1
    bad_argument:       int = 2
    bad_config:         int = 3
    keyboard_interrupt: int = 4
    runtime_error:      int = 5
    uncaught_exception: int = 6


# global shared instance
exit_status = ExitStatus()


class Application(abc.ABC):
    """
    Abstract base class for all application interfaces.

    An application is typically initialized with one of the factory methods
    :func:`~from_namespace` or :func:`~from_cmdline`. These parse command-line
    arguments using the member :class:`~Interface`. Direct initialization takes
    named parameters and are simply assigned to the instance. These should be
    existing class-level attributes with annotations.
    """

    interface: cli.Interface = None
    ALLOW_NOARGS: bool = False

    shared: Namespace = None

    exceptions: Dict[Type[Exception], Callable[[Exception], int]] = dict()
    log_critical: Callable[[str], None] = log.critical
    log_exception: Callable[[str], None] = log.exception

    def __init__(self, **parameters) -> None:
        """Direct initialization sets `parameters`."""
        for name, value in parameters.items():
            setattr(self, name, value)

    @classmethod
    def from_cmdline(cls: Type[TApp], cmdline: List[str] = None) -> TApp:
        """Initialize via command-line arguments (e.g., `sys.argv`)."""
        return cls.from_namespace(cls.interface.parse_args(cmdline))

    @classmethod
    def from_namespace(cls: Type[TApp], namespace: cli.Namespace) -> TApp:
        """Initialize via existing namespace/namedtuple."""
        return cls(**vars(namespace))

    @classmethod
    def main(cls, cmdline: List[str] = None, shared: Namespace = None) -> int:
        """
        Entry-point for application.
        This is a try-except block that handles standard scenarios.

        See Also:
            :data:`~Application.exceptions`
        """
        try:
            if not cmdline:
                if hasattr(cls, 'ALLOW_NOARGS') and cls.ALLOW_NOARGS is True:
                    pass
                else:
                    print(cls.interface.usage_text)
                    return exit_status.usage

            with cls.from_cmdline(cmdline) as app:
                if shared is not None:
                    app.shared = Namespace(shared) if not app.shared else Namespace({**shared, **app.shared})
                app.run()

            return exit_status.success

        except cli.HelpOption as help_text:
            print(help_text)
            return exit_status.success

        except cli.VersionOption as version:
            print(*version.args)
            return exit_status.success

        except cli.ArgumentError as error:
            cls.log_critical(error)
            return exit_status.bad_argument

        except KeyboardInterrupt:
            cls.log_critical('keyboard-interrupt: going down now!')
            return exit_status.keyboard_interrupt

        except Exception as error:
            for exc_type, exc_handler in cls.exceptions.items():
                if isinstance(error, exc_type):
                    return exc_handler(error)
            cls.log_exception('uncaught exception occurred!')
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


class CompletedCommand(Exception):
    """Contains the exit status of a member application's main method."""


class ApplicationGroup(Application):
    """
    A group entry-point delegates to member `Applications`.
    """

    interface: cli.Interface = None
    commands: Dict[str, Application] = None
    command: str = None

    ALLOW_PARSE: bool = False
    cmdline: List[str] = None

    exceptions = {
        CompletedCommand: (lambda cmd: int(cmd.args[0]))
    }

    @classmethod
    def from_cmdline(cls: Type[TAppGrp], cmdline: List[str] = None) -> TAppGrp:
        """Initialize via command-line arguments (e.g., `sys.argv`)."""
        if not cmdline:
            return super().from_cmdline(cmdline)  # noqa: FIXME: typing
        else:
            if cls.ALLOW_PARSE is True and not any(arg in cmdline for arg in {'-h', '--help'}):
                known, remainder = cls.interface.parse_known_intermixed_args(cmdline)
                self = super().from_namespace(known)
                self.cmdline = remainder
                self.shared = Namespace(vars(known))
                self.shared.pop('command')
            else:
                first, *remainder = cmdline
                self = super().from_cmdline([first, ])
                self.cmdline = list(remainder)
            return self  # noqa: FIXME: typing

    def run(self) -> None:
        """Delegate to member application."""
        if self.command in self.commands:
            app = self.commands[self.command]
            status = app.main(self.cmdline, shared=self.shared)
            raise CompletedCommand(status)
        else:
            raise cli.ArgumentError(f'unrecognized command: {self.command}')
