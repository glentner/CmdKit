# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Application class implementation."""


# type annotations
from __future__ import annotations
from typing import List, Dict, Callable, NamedTuple, Type, TypeVar

# standard libs
import abc
import sys
import logging

# internal libs
from cmdkit.cli import Interface, HelpOption, VersionOption, ArgumentError
from cmdkit.namespace import Namespace

# public interface
__all__ = ['exit_status', 'Application', 'ApplicationGroup', 'CompletedCommand']


TApp = TypeVar('TApp', bound='Application')
TAppGrp = TypeVar('TAppGrp', bound='ApplicationGroup')


log = logging.getLogger(__name__)


def _last_resort_would_print(logger: logging.Logger, level: int) -> bool:
    """
    True if Python's last-resort handler would print a record at `level` from `logger`
    were the :class:`logging.NullHandler` on the `cmdkit` logger not there.

    This follows the decision in :meth:`logging.Logger.callHandlers`. Nothing is printed
    if the logger is not enabled for `level` (a disabled logger, a logger level above `level`,
    or :func:`logging.disable`), or if :data:`logging.lastResort` is unset or above `level`.
    Otherwise the logger and its ancestors are searched for as long as they propagate,
    and any handler found, whatever its level, means the application has configured logging.
    The one exception is an exact :class:`logging.NullHandler` on the `cmdkit` logger,
    which the library attaches at import.
    """
    if not logger.isEnabledFor(level):
        return False
    if logging.lastResort is None or level < logging.lastResort.level:
        return False
    current = logger
    while current is not None:
        for handler in current.handlers:
            if current.name == 'cmdkit' and type(handler) is logging.NullHandler:
                continue
            return False
        if not current.propagate:
            break
        current = current.parent
    return True


# NOTE: In next major release this will be made into an Enum
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

    interface: Interface = None
    ALLOW_NOARGS: bool = False

    shared: Namespace = None

    exceptions: Dict[Type[Exception], Callable[[Exception], int]] = dict()
    log_critical: Callable[[str], None] = log.critical
    log_exception: Callable[[str], None] = log.exception

    @classmethod
    def handle_help(cls, message: str) -> None:
        print(message)

    @classmethod
    def handle_version(cls, *args) -> None:
        print(*args)

    @classmethod
    def handle_usage(cls, message: str) -> None:
        print(message)

    def __init__(self, **parameters) -> None:
        """Direct initialization sets `parameters`."""
        for name, value in parameters.items():
            setattr(self, name, value)

    @classmethod
    def from_cmdline(cls: Type[TApp], cmdline: List[str] = None) -> TApp:
        """Initialize via command-line arguments (e.g., `sys.argv`)."""
        return cls.from_namespace(cls.interface.parse_args(cmdline))

    @classmethod
    def from_namespace(cls: Type[TApp], namespace: Namespace) -> TApp:
        """Initialize via existing namespace/namedtuple."""
        return cls(**vars(namespace))

    @classmethod
    def main(cls, cmdline: List[str] = None, shared: Namespace = None) -> int:
        """
        Entry-point for application.
        This is a try-except block that handles standard scenarios.

        An :class:`~cmdkit.cli.ArgumentError` is passed to :data:`~Application.log_critical`
        and ``exit_status.bad_argument`` is returned. If ``log_critical`` is the default and
        Python's last-resort handler would print the record (no handler of the application's
        would see it, and the ``cmdkit.app`` logger is not silenced), the message is also
        written as is to ``sys.stderr``, followed by a newline.

        See Also:
            :data:`~Application.exceptions`
            :data:`~Application.log_critical`
        """
        try:
            if not cmdline:
                if hasattr(cls, 'ALLOW_NOARGS') and cls.ALLOW_NOARGS is True:
                    pass
                else:
                    cls.handle_usage(cls.interface.usage_text)
                    return exit_status.usage

            with cls.from_cmdline(cmdline) as app:
                if shared is not None:
                    app.shared = Namespace(shared) if not app.shared else Namespace({**shared, **app.shared})
                app.run()

            return exit_status.success

        except HelpOption as help_opt:
            cls.handle_help(*help_opt.args)
            return exit_status.success

        except VersionOption as version:
            cls.handle_version(*version.args)
            return exit_status.success

        except ArgumentError as error:
            cls.log_critical(error)
            if cls.log_critical == log.critical and _last_resort_would_print(log, logging.CRITICAL):
                print(error, file=sys.stderr)
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
    """A group entry-point delegates to a member `Application`."""

    interface: Interface = None
    commands: Dict[str, Type[Application]] = None
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
            return super(ApplicationGroup, cls).from_cmdline(cmdline)
        else:
            if cls.ALLOW_PARSE is True and not any(arg in cmdline for arg in {'-h', '--help'}):
                known, remainder = cls.interface.parse_known_intermixed_args(cmdline)
                self = super(ApplicationGroup, cls).from_namespace(known)
                self.cmdline = remainder
                self.shared = Namespace(vars(known))
                self.shared.pop('command')
            else:
                first, *remainder = cmdline
                self = super(ApplicationGroup, cls).from_cmdline([first, ])
                self.cmdline = list(remainder)
            return self

    def run(self) -> None:
        """Delegate to member application."""
        if self.command in self.commands:
            app = self.commands[self.command]
            status = app.main(self.cmdline, shared=self.shared)
            raise CompletedCommand(status)
        else:
            raise ArgumentError(f'unrecognized command: {self.command}')
