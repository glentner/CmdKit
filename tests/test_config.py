# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""Unit tests for `cmdkit.config` behavior and interfaces."""


# external libs
import pytest

# internal libs
from cmdkit.config import Namespace


# def test_namespace_interface() -> None:
#     """Create a dummy namespace and verify the interface is functional."""

#     # dummy namespace
#     ns = Namespace({'a': 'apple', 'b': 'banana'})

#     # __getattr__ exposes `Namespace._data` dict.
#     # attribute assignment behaves normally if not in dict ...
#     # because we need sub-classes to have special variables.
#     assert ns.a == 'apple'
#     ns.c = 'other'
#     with pytest.raises(KeyError):
#         ns._data['c'] 


#     # __setattr__ inserts into `Namespace._data`.
#     ns.a = 3.14
#     assert ns._data['a'] == 3.14

#     # nested dictionaries
#     ns.b = {'x': 1, 'y': 2, 'z': 3}
#     assert ns.b.y == 2  # pylint: disable=no-member
#     ns.b.z = 4
#     assert ns.b.z == 4  # pylint: disable=no-member