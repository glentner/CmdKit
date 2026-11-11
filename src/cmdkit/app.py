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


def _hidden_by_null_handler(logger: logging.Logger, level: int, msg: object) -> bool:
    """
    True if the :class:`logging.NullHandler` cmdkit attaches to its logger at import is the only
    reason Python's last-resort handler did not print a record with `msg` at `level` from `logger`.

    This follows :meth:`logging.Logger.handle` and :meth:`logging.Logger.callHandlers` in order,
    and is false wherever Python would print nothing anyway: the logger is not enabled for `level`
    (a disabled logger, a logger level above `level`, or :func:`logging.disable`), the logger's
    own filters reject the record, or :data:`logging.lastResort` is unset or above `level`.
    Otherwise the logger and its ancestors are searched for as long as they propagate. Any handler
    found, whatever its level, other than cmdkit's own (recognised by the mark set on it where the
    package attaches it) means the application has configured logging: false. That includes a
    :class:`logging.NullHandler` the application adds to the `cmdkit` logger itself to silence it.
    If no handler is found at all, Python's last resort has already printed the record: also
    false, so the message appears only once.
    """
    if not logger.isEnabledFor(level):
        return False
    if not logger.filter(logger.makeRecord(logger.name, level, '(unknown file)', 0, msg, (), None)):
        return False
    if logging.lastResort is None or level < logging.lastResort.level:
        return False
    found = False
    current = logger
    while current is not None:
        for handler in current.handlers:
            if getattr(handler, '_cmdkit_library_handler', False) is not True:
                return False
            found = True
        if not current.propagate:
            break
        current = current.parent
    return found


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
        and ``exit_status.bad_argument`` is returned. If ``log_critical`` is the default and the
        :class:`~logging.NullHandler` cmdkit attaches to its own logger is the only reason
        Python's last-resort handler did not print the record (no handler of the application's
        is found, and the ``cmdkit.app`` logger is neither silenced nor filtering the record
        out), the message is also written as is to ``sys.stderr``, followed by a newline.
        Where no handler is found at all, Python's last resort prints the record itself, and
        that line stands alone. A :class:`~logging.NullHandler` the application adds to the
        ``cmdkit`` logger is a handler of the application's, and keeps the message silent.

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
            if cls.log_critical == log.critical and _hidden_by_null_handler(log, logging.CRITICAL, error):
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
    def main(cls, cmdline: List[str] = None, shared: Namespace = None) -> int:
        """
        Entry-point for application group.

        By default, an empty ``cmdline`` prints the usage text and returns ``exit_status.usage``,
        as for any :class:`Application`. If the group sets ``ALLOW_NOARGS = True`` and its
        interface rejects the bare command line (its ``command`` positional is required, and
        nothing supplies it), the command line is taken as ``['--help']`` instead: the help
        text is printed and ``exit_status.success`` is returned. A group whose interface
        accepts the bare command line (its ``command`` is optional) proceeds to ``run``, as
        with any :class:`Application`. As there, ``None`` lets the interface read
        ``sys.argv``, so arguments there are dispatched or reported as usual.
        Otherwise this is :meth:`Application.main`.

        Example:
            >>> class MyGroup(ApplicationGroup):
            ...     interface = Interface('mygroup', 'usage: mygroup <command>', 'help: mygroup <command>')
            ...     command: str = None
            ...     interface.add_argument('command')
            ...     ALLOW_NOARGS = True
            >>> MyGroup.main([])
            help: mygroup <command>
            0
        """
        if not cmdline and cls.ALLOW_NOARGS is True:
            try:
                cls.interface.parse_args(cmdline)
            except ArgumentError:
                cmdline = ['--help', ]
        return super(ApplicationGroup, cls).main(cmdline, shared=shared)

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
