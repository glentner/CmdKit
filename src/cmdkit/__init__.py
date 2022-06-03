# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Package initialization for CmdKit."""


# package attributes
from .__meta__ import (__pkgname__, __version__, __authors__, __contact__,
                       __license__, __copyright__, __description__)

# null-handler for library
import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())
