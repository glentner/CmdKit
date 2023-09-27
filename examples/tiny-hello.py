#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Tiny example script using CmdKit."""


# type annotations
from __future__ import annotations

# standard libs
import os
import sys

# external libs
from cmdkit import Application, Interface

# metadata
version = '0.1.0'

prog_name = os.path.basename(sys.argv[0])
usage_text = f"""\
Usage:
  {prog_name} [-v] NAME
  {__doc__}\
"""

help_text = f"""\
{usage_text}

Arguments:
  NAME                  Name of person to greet.

Options:
  -v, --version         Print version and exit.
  -h, --help            Print this message and exit.\
"""


class TinyApp(Application):
    """Application class for tiny-script program."""

    interface = Interface(prog_name, usage_text, help_text)
    interface.add_argument('-v', '--version', action='version', version=version)

    name: str
    interface.add_argument('name')

    def run(self: TinyApp) -> None:
        """Run program."""
        print(f'Hello, {self.name}!')


if __name__ == '__main__':
    sys.exit(TinyApp.main(sys.argv[1:]))
