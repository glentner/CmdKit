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
Agent implementation.
"""

# standard libs
import time
from multiprocessing import Process
from abc import abstractmethod

# internal libs
from .service import Service
from ..logging import log


class Agent(Service):
    """An agent spawns 'task' jobs with a specified periodicity."""

    def __init__(self, name: str, interval: float, daemon: bool = False) -> None:
        """
        Initialize an Agent.

        Arguments
        ---------
        name: str
            Unique identifier (used for runtime pid file).
        interval: float
            Seconds to wait between successive tasks.

        daemon: bool = False
            Alter behavior to act in daemon mode.
        """
        self.name = name
        self.interval = interval
        super().__init__(pidfile, daemon=daemon)

    @property
    def id(self) -> str:
        """Unique identifier for Agent."""
        return self.__id

    @id.setter
    def id(self, other: str) -> None:
        """Assign unique identifier for Agent."""
        value = str(other)
        for badchar in ('/', ' ', '`'):
            if badchar in value:
                raise ValueError(f'{self.__class__.__name__}.id is used to create the pidfile, ',
                                 f'it cannot contain \"{badchar}\".')
        self.__id = value

    @property
    def period(self) -> float:
        """The period the Agent sleeps between spawning tasks."""
        return self.__period

    @period.setter
    def period(self, other: float) -> None:
        """Assign the period used to sleep between spawning tasks."""
        value = float(other)
        if value <= 0:
            raise ValueError(f'{self.__class__.__name__}.period expects a positive value, '
                             f'given {value}.')
        self.__period = value

    @abstractmethod
    def task(self) -> None:
        """A task must be defined for all Agents."""
        raise NotImplementedError()

    def spawn_task(self) -> Process:
        """Fork a new child process to run 'task'."""
        p = Process(target=self.task)
        p.start()
        log.debug(f'{self.__class__.__name__}: new task started at {p.pid}.')
        return p

    @property
    def pidfile(self) -> str:
        """The process ID file (usually in /var/run/)."""
        return f'{IOT_RUN}/iot-{self.id}.pid'

    def run(self) -> None:
        """An Agent spawns 'task' jobs with a specified sleep period."""
        task = self.spawn_task()
        while True:
            time.sleep(self.period)
            if task.is_alive():
                log.warning(f'{self.__class__.__name__}:{self.id}: task not finished '
                            f'at {task.pid}, waiting...')
            task.join()
            task = self.spawn_task()
