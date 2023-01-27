# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Package initialization for CmdKit."""


# standard libs
import logging

# null-handler for library interface
logging.getLogger(__name__).addHandler(logging.NullHandler())

# package metadata
__version__   = '2.6.1'
