# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Unit tests for `cmdkit.service`."""

# standard libs
import os
import time
import random
import string
from multiprocessing import Process
from subprocess import check_call, CalledProcessError

# external libs
import pytest

# internal libs
from cmdkit.service.daemon import Daemon
from cmdkit.service.agent import Agent
from cmdkit.logging import log, ConsoleHandler, LEVELS


# setup logging in debug mode
log.handlers.append(ConsoleHandler(LEVELS[0]))


PID_PATH = '/tmp/cmdkit_tests/run/{}.pid'
os.makedirs(os.path.dirname(PID_PATH), exist_ok=True)


class DemoDaemon(Daemon):
    """Example Daemon implementation does nothing."""

    PIDFILE = PID_PATH.format('test_daemon')

    def run(self) -> None:
        log.debug(f'running {self.pidfile}')
        while True:
            time.sleep(1)

    @classmethod
    def test(cls, action: str) -> None:
        """Create the daemon instance and either start/stop/restart."""
        app = cls(cls.PIDFILE)
        getattr(app, action)()


def test_service_daemon_start_stop() -> None:
    """Start the test daemon."""

    # start the daemon
    log.debug(f'starting daemon')
    p = Process(target=DemoDaemon.test, args=('start', ))
    p.start(); p.join()

    # wait for PIDFILE to be created
    time.sleep(1)

    # verify exists and scrape PID
    with open(DemoDaemon.PIDFILE, mode='r') as pidfile:
        PID = int(pidfile.read().strip())
        log.debug(f'daemon had pid={PID}')

    # verify that daemon process is running
    check_call(['ps', str(PID)])  # raises CalledProcessError if `PID` invalid

    log.debug(f'stopping daemon')
    p = Process(target=DemoDaemon.test, args=('stop', ))
    p.start(); p.join()

    assert not os.path.exists(DemoDaemon.PIDFILE)
    with pytest.raises(CalledProcessError):
        check_call(['ps', str(PID)])


class DemoAgent(Agent):
    """An agent that does nothing."""

    name = 'demo'
    interval = 1
    pid_dir = os.path.dirname(PID_PATH)

    def task(self) -> None:
        with open(f'{self.pid_dir}/{self.name}.dat', mode='a') as f:
            print('task complete', file=f)

    @classmethod
    def test(cls, action: str) -> None:
        """Create the daemon instance and either start/stop/restart."""
        app = cls(daemon=True)
        getattr(app, action)()


def test_agent() -> None:
    """Test that the agent starts and runs its task three times."""

    # clear previous data
    datfile = f'{DemoAgent.pid_dir}/{DemoAgent.name}.dat'
    if os.path.exists(datfile):
        os.remove(datfile)

    # start the daemon
    log.debug(f'starting agent')
    p = Process(target=DemoAgent.test, args=('start', ))
    p.start(); p.join()

    # verify exists and scrape PID
    pidfile = f'{DemoAgent.pid_dir}/{DemoAgent.name}.pid'
    with open(pidfile, mode='r') as f:
        PID = int(f.read().strip())
        log.debug(f'agent had pid={PID}')

    # verify that daemon process is running
    check_call(['ps', str(PID)])  # raises CalledProcessError if `PID` invalid

    # allow for at least three tasks to execute
    time.sleep(3)

    log.debug(f'stopping agent')
    p = Process(target=DemoAgent.test, args=('stop', ))
    p.start(); p.join()

    assert not os.path.exists(pidfile)
    with pytest.raises(CalledProcessError):
        check_call(['ps', str(PID)])

    # check data from task
    assert os.path.exists(datfile)
    with open(datfile, mode='r') as f:
        lines = [line.strip() for line in f.readlines()]

    assert len(lines) >= 3
    assert all(line == 'task complete' for line in lines)