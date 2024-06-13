# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Guarded execution Provider. The decorator based provider extends functionality by allowing
the safe and symantically simple support for guarded execution of applications(groups).

TODO:
    - unit testing
    - doctests and examples
    - add more guards as needed
"""

# type annotations
from __future__ import annotations
from typing import cast, Any, Callable, Optional, TypeVar, Union
from collections.abc import Container

# system libraries
import os
import grp
import logging
from functools import wraps

# static analysis
F = TypeVar('F', bound = Callable[..., Any])
D = Callable[[F], F]

logger = logging.getLogger(__name__)

class AuthError(Exception):
    """Raised when cannot authenticate user."""

class LibraryError(Exception):
    """Raised when handling errors raised by library or support modules."""

def authorized(*, groups: Optional[Union[str, Container[str]]] = None,
               message: str = 'User does not have permissions for this command!',
               root: Optional[bool] = None, users: Optional[Union[str, Container[str]]] = None) -> D:
    """Decorator which assures that only allowed users may execute the decorated funtion; this is based on 
    checking the executing process against a number of optional criteria. The various options (e.g., groups and users) 
    represent intersection operators, while the collection within an option represent union operators."""
    def decorator(function: F) -> F:
        @wraps(function)
        def wrapper(*args, **kwargs):
            try:
                if root is not None:
                    assert os.geteuid() == 0 if root else os.geteuid() != 0
                if users is not None:
                    if isinstance(users, str):
                        assert os.getlogin() == users
                    else:
                        assert os.getlogin() in users
                if groups is not None:
                    if isinstance(groups, str):
                        assert grp.getgrnam(groups).gr_gid in os.getgroups()
                    else:
                        assert any(grp.getgrnam(g).gr_gid in os.getgroups() for g in groups)
            except AssertionError:
                raise AuthError(message)
            except KeyError:
                raise LibraryError(f'Group <{group}> not found in system groups!')
            logger.debug(f'authorized -- Guarded a call into <{function.__name__}>.')
            return function(*args, **kwargs)
        return cast(F, wrapper)
    return decorator

