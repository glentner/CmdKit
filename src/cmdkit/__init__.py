# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Package initialization for CmdKit."""


# standard libs
import logging

# null-handler for library interface
logging.getLogger(__name__).addHandler(logging.NullHandler())

# package metadata
__pkgname__   = 'cmdkit'
__version__   = '2.6.1'
__authors__   = 'Geoffrey Lentner'
__contact__   = 'glentner@purdue.edu'
__license__   = 'Apache License'
__copyright__ = 'Geoffrey Lentner 2019-2022'
__description__ = 'A command-line utility toolkit for Python.'
