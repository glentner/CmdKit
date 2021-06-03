# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Package initialization for CmdKit."""


import logging
from .__meta__ import (__pkgname__, __version__, __authors__, __contact__,\
                       __license__, __copyright__, __description__)


# top-level logger
logging.getLogger(__name__).addHandler(logging.NullHandler())
