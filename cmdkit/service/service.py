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
Implementation of Service class.
"""

# internal libs
from .daemon import Daemon


class Service(Daemon):
    """
    A Service can be run directly and _optionally_ daemonized.

    Like `cmdkit.service.daemon.Daemon`, a `run` method must be defined
    that implements the main business logic (i.e., the entry-point).
    """

    _is_daemon: bool = False

    def __init__(self, pidfile: str, daemon: bool = False) -> None:
        """
        Initialization. You must call `.start()` before `.run()` is called.

        Arguments
        ---------
        pidfile: str
            Path to a process ID file. This file is created with
            the process ID so it can be stopped later.

        daemonize: bool (default=False)
            Run service as a daemon process.
        """
        super().__init__(pidfile)
        self.is_daemon = daemon

    def daemonize(self) -> None:
        """Overrides the Daemon implementation if not `is_daemon`."""
        if self.is_daemon:
            super().daemonize()

    @property
    def is_daemon(self) -> bool:
        """Is this service able to become a daemon."""
        return self.__is_daemon

    @is_daemon.setter
    def is_daemon(self, other: bool) -> None:
        """Assign whether this service can become a daemon."""
        if other in (True, False, 0, 1):
            self.__is_daemon = bool(other)
        else:
            raise ValueError(f'{self.__class__.__name__}.is_daemon expects True/False.')
