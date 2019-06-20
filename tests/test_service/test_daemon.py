# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Unit tests for `cmdkit.service.daemon`."""

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
from cmdkit import logging
log = logging._get_debugger()
logging.log = log

PID_PATH = '/tmp/cmdkit_tests/run/{}.pid'
os.makedirs(os.path.dirname(PID_PATH), exist_ok=True)

from cmdkit.service.daemon import Daemon


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
    log.debug(f'starting DemoDaemon')
    p = Process(target=DemoDaemon.test, args=('start', ))
    p.start(); p.join()

    # wait for PIDFILE to be created
    time.sleep(1)

    # verify exists and scrape PID
    with open(DemoDaemon.PIDFILE, mode='r') as pidfile:
        PID = int(pidfile.read().strip())
        log.debug(f'DemoDaemon.pidfile had pid={PID}')

    # verify that daemon process is running
    check_call(['ps', str(PID)])  # raises CalledProcessError if `PID` invalid

    log.debug(f'stopping DemoDaemon')
    p = Process(target=DemoDaemon.test, args=('stop', ))
    p.start(); p.join()

    assert not os.path.exists(DemoDaemon.PIDFILE)
    with pytest.raises(CalledProcessError):
        check_call(['ps', str(PID)])