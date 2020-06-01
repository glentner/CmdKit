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
from datetime import datetime, timedelta
from multiprocessing import Process
from abc import abstractmethod

# internal libs
from .service import Service
from ..logging import log


class Agent(Service):
    """An agent runs 'task' jobs with on a specified interval."""

    name: str = None
    interval: float = None
    pid_dir: str = '/var/run'

    def __init__(self, daemon: bool = False) -> None:
        """
        Initialize an Agent.

        Arguments
        ---------
        daemon: bool = False
            Alter behavior to act in daemon mode.
        """
        super().__init__(f'{self.pid_dir}/{self.name}.pid', daemon=daemon)

    @abstractmethod
    def task(self) -> None:
        """A task must be defined for all Agents."""
        raise NotImplementedError()

    def run(self) -> None:
        """An Agent spawns 'task' jobs with a specified sleep period."""
        while True:
            start_time = datetime.now()
            start_next = start_time + timedelta(seconds=self.interval)
            self.task()
            if datetime.now() < start_next:
                time.sleep((start_next - datetime.now()).total_seconds())
