#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Full example script using CmdKit."""


# type annotations
from __future__ import annotations
from typing import IO

# standard libs
import os
import sys
import json

# external libs
from cmdkit.app import Application, exit_status
from cmdkit.cli import Interface
from cmdkit.config import Namespace, Configuration
from cmdkit.platform import AppContext
from cmdkit.logging import Logger, logging_styles, level_by_name

# metadata
version = '0.1.0'
appname = 'FullHello'
program = os.path.basename(sys.argv[0])


default_config = Namespace({
    'logging': {
        'style': 'short',
        'level': 'info'
    }
    # Add more configuration here ...
})


try:
    context = AppContext.default(appname=appname, create_dirs=True)
    config = Configuration.from_local(
        env=True,
        prefix=appname.upper(),
        default=default_config,
        system=context.path.system.config,
        user=context.path.user.config,
        local=context.path.local.config,
    )

    log = Logger.default(program, format=logging_styles[config.logging.style.lower()]['format'])
    log.setLevel(level_by_name[config.logging.level.upper()])

except Exception as error:
    print(f'error: {program}: {error}', file=sys.stderr)
    sys.exit(exit_status.bad_config)


usage_text = f"""\
Usage:
{program} [-v] [NAME | --config | --site] [-o FILE]
{__doc__}\
"""

help_text = f"""\
{usage_text}

Arguments:
  NAME                  Name of person to greet.

Options:
  -c, --config          Show configuration and exit.
  -s, --site            Show site paths and exit.
  -o, --output    FILE  Path to output file.
  -v, --version         Print version and exit.
  -h, --help            Print this message and exit.\
"""


site_text = f"""\
[system]
data:   {context.path.system.lib}
logs:   {context.path.system.log}
config: {context.path.system.config}

[user]
data:   {context.path.user.lib}
logs:   {context.path.user.log}
config: {context.path.user.config}

[local]
data:   {context.path.local.lib}
logs:   {context.path.local.log}
config: {context.path.local.config}
"""

site_text = site_text.replace(
    f'[{context.default_site}]',
    f'[{context.default_site}] (default)',
)


class FullHello(Application):
    """Application class for program."""

    interface = Interface(program, usage_text, help_text)
    interface.add_argument('-v', '--version', action='version', version=version)

    name: str = None
    interface.add_argument('name', nargs='?', default=None)

    show_config: bool = False
    show_site: bool = False
    mode = interface.add_mutually_exclusive_group()
    mode.add_argument('-c', '--config', action='store_true', dest='show_config')
    mode.add_argument('-s', '--site', action='store_true', dest='show_site')

    outpath: str = '-'
    output_stream: IO = sys.stdout
    interface.add_argument('-o', '--output', dest='outpath', default=outpath)

    def run(self: FullHello) -> None:
        """Run program."""
        if self.show_config:
            log.info('Showing configuration')
            print(json.dumps(dict(config), indent=4), file=self.output_stream)
        elif self.show_site:
            log.info('Showing site details')
            print(site_text, file=self.output_stream)
        else:
            log.info('Greeting user')
            print(f'Hello, {self.name}!', file=self.output_stream)

    def __enter__(self: FullHello) -> Application:
        """Open output file path."""
        if self.outpath != '-':
            self.output_stream = open(self.outpath, mode='w')
        return super().__enter__()

    def __exit__(self: FullHello, *exc) -> None:
        """Close resources."""
        if self.output_stream is not sys.stdout:
            self.output_stream.close()
        return super().__exit__(*exc)


if __name__ == '__main__':
    sys.exit(FullHello.main(sys.argv[1:]))
