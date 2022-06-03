# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Agent class implementation."""


# standard libs
import time
from datetime import datetime, timedelta
from abc import abstractmethod

# internal libs
from .service import Service


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
