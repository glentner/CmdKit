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


# standard libs
import os
from io import StringIO
from string import ascii_letters

# external libs
import pytest
from hypothesis import given
from hypothesis.strategies import lists, text, integers

# internal libs
from cmdkit.config import Namespace, Environ, Configuration


# ensure temporary directory exists
TMPDIR = '/tmp/cmdkit/config'
os.makedirs(TMPDIR, exist_ok=True)


def test_namespace_init() -> None:
    """Construct a namespace from a dictionary compatable initialization."""
    assert (Namespace({'A': 1, 'B': 2, 'C': {'X': 'hello', 'Y': 'world'}}) ==
            Namespace([('A', 1), ('B', 2), ('C', Namespace([('X', 'hello'), ('Y', 'world')]))]) ==
            Namespace(A=1, B=2, C=Namespace(X='hello', Y='world')))


# dummy data for testing namespace behavior
KEYS, VALUES = list(ascii_letters), range(len(ascii_letters))
DATA = dict(zip(KEYS, VALUES))


def test_namespace_keys_and_values() -> None:
    """Ensure .keys() functions as expected."""
    assert list(Namespace(DATA).keys()) == list(DATA.keys())
    assert list(Namespace(DATA).values()) == list(DATA.values())


def test_namespace_get() -> None:
    """Test Namespace[], Namespace.get()."""
    ns = Namespace(DATA)
    for key, value in zip(KEYS, VALUES):
        assert ns[key] == ns.get(key) == value


def test_namespace_set() -> None:
    """Test Namespace[] setter."""
    ns = Namespace()
    for key, value in zip(KEYS, VALUES):
        ns[key] = value
    assert list(ns.keys()) == list(DATA.keys())
    assert list(ns.values()) == list(DATA.values())


def test_namespace_setdefault() -> None:
    """Test Namespace.setdefault()."""
    ns = Namespace()
    for key, value in zip(KEYS, VALUES):
        ns.setdefault(key, value)
    assert list(ns.keys()) == list(DATA.keys())
    assert list(ns.values()) == list(DATA.values())


def test_namespace_iterate() -> None:
    """Test that Namespace can use [] syntax."""
    ns = Namespace(DATA)
    for i, (key, value) in enumerate(ns.items()):
        assert key == KEYS[i]
        assert value == VALUES[i]


def test_namespace_update_simple() -> None:
    """Test Namespace.update() behavior"""
    ns = Namespace()
    for i, (key, value) in enumerate(DATA.items()):
        ns.update({key: value})
    assert list(ns.keys()) == list(DATA.keys())
    assert list(ns.values()) == list(DATA.values())


def test_namespace_update_complex() -> None:
    """Test Namespace.update() behavior"""

    ns = Namespace({'a': {'x': 1, 'y': 2}})

    ns.update({'b': {'z': 3}})
    assert ns == {'a': {'x': 1, 'y': 2}, 'b': {'z': 3}}

    ns.update({'a': {'z': 3}})
    assert ns == {'a': {'x': 1, 'y': 2, 'z': 3}, 'b': {'z': 3}}

    ns.update({'a': {'x': 5}})
    assert ns == {'a': {'x': 5, 'y': 2, 'z': 3}, 'b': {'z': 3}}


TEST_DICT = {
    'a': {'a': 1, 'aa': 'aaa'},
    'b': {'b': 2, 'bb': 'bbb'},
    'c': {'c': 3, 'cc': 'ccc'}
}


TEST_TOML = """\
[a]
a = 1
aa = "aaa"

[b]
b = 2
bb = "bbb"

[c]
c = 3
cc = "ccc"
"""


TEST_YAML = """\
a:
    a: 1
    aa: aaa
b:
    b: 2
    bb: bbb
c:
    c: 3
    cc: ccc
"""


TEST_JSON = """\
{
    "a": {
        "a": 1,
        "aa": "aaa"
    },
    "b": {
        "b": 2,
        "bb": "bbb"
    },
    "c": {
        "c": 3,
        "cc": "ccc"
    }
}
"""


TEST_ENV = """
CMDKIT_A_A=1
CMDKIT_A_AA=aaa
CMDKIT_B_B=2
CMDKIT_B_BB=bbb
CMDKIT_C_C=3
CMDKIT_C_CC=ccc
"""


FACTORIES = {'toml': TEST_TOML,
             'yaml': TEST_YAML,
             'json': TEST_JSON}


def test_namespace_factories() -> None:
    """Test all implemented factory equivalents."""

    # base case
    BASE = Namespace(TEST_DICT)

    # write all test data to local files
    for ftype, data in FACTORIES.items():
        with open(f'{TMPDIR}/{ftype}.{ftype}', mode='w') as output:
            output.write(data)

    # test both file-like object and file path modes of construction
    assert (Namespace(TEST_DICT) ==
            Namespace.from_toml(StringIO(TEST_TOML)) == Namespace.from_toml(f'{TMPDIR}/toml.toml') ==
            Namespace.from_yaml(StringIO(TEST_YAML)) == Namespace.from_yaml(f'{TMPDIR}/yaml.yaml') ==
            Namespace.from_json(StringIO(TEST_JSON)) == Namespace.from_json(f'{TMPDIR}/json.json'))


def test_environ() -> None:
    """Test environment variable initialization along with Environ.reduce()."""

    # clean environment of any existing variables with the prefix
    PREFIX = 'CMDKIT'
    for var in dict(os.environ):
        if var.startswith(PREFIX):
            os.environ.pop(var)

    # populate environment with test variables
    for line in TEST_ENV.strip().split('\n'):
        field, value = line.strip().split('=')
        os.environ[field] = value

    # test base level Namespace|Environ equivalence
    assert Namespace.from_env(prefix=PREFIX) == Environ(prefix=PREFIX)

    # test reduction (non-string values are not automatically coerced)
    env = Environ(prefix=PREFIX).reduce()
    for part in list('abc'):
        env.update({part: {part: int(env[part][part])}})

    assert env == Namespace(TEST_DICT)


def test_configuration() -> None:
    """Test configuration initialization."""

    # test namespaces
    ns_a = Namespace(TEST_DICT)
    ns_b = Namespace.from_toml(StringIO(TEST_TOML))
    ns_c = Namespace.from_yaml(StringIO(TEST_YAML))
    ns_d = Namespace.from_json(StringIO(TEST_JSON))

    # initialize construction results in member namespaces
    cfg = Configuration(A=ns_a, B=ns_b)
    assert dict(cfg) == cfg.namespaces['A'] == ns_a == cfg.namespaces['B'] == ns_b

    # extend the configuration
    cfg.extend(C=ns_c, D=ns_d)
    assert (cfg.namespaces['A'] == ns_a ==
            cfg.namespaces['B'] == ns_b ==
            cfg.namespaces['C'] == ns_c ==
            cfg.namespaces['D'] == ns_d ==
            dict(cfg))

    # keys() and values() are available
    assert list(cfg.keys()) == list(ns_a.keys())
    assert list(cfg.values()) == list(ns_a.values())


def test_configuration_blending() -> None:
    """Test that configuration applied depth-first blending of namespaces."""

    ns_a = Namespace({'a': {'x': 1, 'y': 2}})
    ns_b = Namespace({'b': {'z': 3}})  # new section
    ns_c = Namespace({'a': {'z': 4}})  # new value in existing section
    ns_d = Namespace({'a': {'x': 5}})  # altered value in existing section

    # configuration blends nested namespaces
    cfg = Configuration(A=ns_a, B=ns_b, C=ns_c, D=ns_d)

    # confirm separate namespaces
    assert cfg.namespaces['A'] == ns_a
    assert cfg.namespaces['B'] == ns_b
    assert cfg.namespaces['C'] == ns_c
    assert cfg.namespaces['D'] == ns_d

    # confirm d << c << b << a look up
    assert cfg['a']['x'] == 5
    assert cfg['a']['y'] == 2
    assert cfg['a']['z'] == 4
    assert cfg['b']['z'] == 3
