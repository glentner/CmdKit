# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for `cmdkit.config` behavior and interfaces."""


# standard libs
import os
from io import StringIO
from string import ascii_letters

# external libs
import pytest

# internal libs
from cmdkit.config import Namespace, Environ, Configuration


# ensure temporary directory exists
TMPDIR = '/tmp/cmdkit/config'
os.makedirs(TMPDIR, exist_ok=True)


# dummy data for testing namespace behavior
KEYS, VALUES = list(ascii_letters), range(len(ascii_letters))
DATA = dict(zip(KEYS, VALUES))


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


FACTORIES = {
    'toml': TEST_TOML, 'tml': TEST_TOML,
    'yaml': TEST_YAML, 'yml': TEST_YAML,
    'json': TEST_JSON
}


class TestNamespace:
    """Unit tests for Namespace."""

    def test_init(self) -> None:
        """Construct a namespace from a dictionary compatible initialization."""
        assert (Namespace({'A': 1, 'B': 2, 'C': {'X': 'hello', 'Y': 'world'}}) ==
                Namespace([('A', 1), ('B', 2), ('C', Namespace([('X', 'hello'), ('Y', 'world')]))]) ==
                Namespace(A=1, B=2, C=Namespace(X='hello', Y='world')))

    def test_keys_and_values(self) -> None:
        """Ensure .keys() functions as expected."""
        assert list(Namespace(DATA).keys()) == list(DATA.keys())
        assert list(Namespace(DATA).values()) == list(DATA.values())

    def test_get(self) -> None:
        """Test Namespace[], Namespace.get()."""
        ns = Namespace(DATA)
        for key, value in zip(KEYS, VALUES):
            assert ns[key] == ns.get(key) == value
            assert ns.get(f'{key}_', False) is False

    def test_set(self) -> None:
        """Test Namespace[] setter."""
        ns = Namespace()
        for key, value in zip(KEYS, VALUES):
            ns[key] = value
        assert list(ns.keys()) == list(DATA.keys())
        assert list(ns.values()) == list(DATA.values())

    def test_setdefault(self) -> None:
        """Test Namespace.setdefault()."""
        ns = Namespace()
        for key, value in zip(KEYS, VALUES):
            ns.setdefault(key, value)
        assert list(ns.keys()) == list(DATA.keys())
        assert list(ns.values()) == list(DATA.values())

    def test_iterate(self) -> None:
        """Test that Namespace can use [] syntax."""
        ns = Namespace(DATA)
        for i, (key, value) in enumerate(ns.items()):
            assert key == KEYS[i]
            assert value == VALUES[i]

    def test_update_simple(self) -> None:
        """Test Namespace.update() behavior"""
        ns = Namespace()
        for i, (key, value) in enumerate(DATA.items()):
            ns.update({key: value})
        assert list(ns.keys()) == list(DATA.keys())
        assert list(ns.values()) == list(DATA.values())

    def test_update_complex(self) -> None:
        """Test Namespace.update() behavior."""

        ns = Namespace({'a': {'x': 1, 'y': 2}})

        ns.update({'b': {'z': 3}})
        assert ns == {'a': {'x': 1, 'y': 2}, 'b': {'z': 3}}

        ns.update({'a': {'z': 3}})
        assert ns == {'a': {'x': 1, 'y': 2, 'z': 3}, 'b': {'z': 3}}

        ns.update({'a': {'x': 5}})
        assert ns == {'a': {'x': 5, 'y': 2, 'z': 3}, 'b': {'z': 3}}

    def test_deep_inplace_assignment(self) -> None:
        """Test Namespace attribute access behavior."""

        ns = Namespace({'a': {'x': 1, 'y': 2}})
        assert isinstance(ns.a, Namespace)
        assert ns.a == {'x': 1, 'y': 2}
        assert ns.a.x == 1 and ns.a.y == 2

        ns.a.x = 3
        assert ns.a.x == 3

    def test_factories(self) -> None:
        """Test all implemented factory equivalents."""

        # write all test data to local files
        for ftype, data in FACTORIES.items():
            with open(f'{TMPDIR}/{ftype}.{ftype}', mode='w') as output:
                output.write(data)

        # test both file-like object and file path modes of construction
        assert (Namespace(TEST_DICT) ==
                Namespace.from_toml(StringIO(TEST_TOML)) == Namespace.from_toml(f'{TMPDIR}/toml.toml') ==
                Namespace.from_yaml(StringIO(TEST_YAML)) == Namespace.from_yaml(f'{TMPDIR}/yaml.yaml') ==
                Namespace.from_json(StringIO(TEST_JSON)) == Namespace.from_json(f'{TMPDIR}/json.json'))

    def test_from_local(self) -> None:
        """Test automatic file type deduction and allow for missing files."""

        # clear existing files
        for ftype in FACTORIES:
            filepath = f'{TMPDIR}/{ftype}.{ftype}'
            if os.path.exists(filepath):
                os.remove(filepath)

        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{TMPDIR}/toml.toml')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{TMPDIR}/yaml.yaml')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{TMPDIR}/json.json')

        assert (Namespace() ==
                Namespace.from_local(f'{TMPDIR}/toml.toml', ignore_if_missing=True) ==
                Namespace.from_local(f'{TMPDIR}/yaml.yaml', ignore_if_missing=True) ==
                Namespace.from_local(f'{TMPDIR}/json.json', ignore_if_missing=True))

        with pytest.raises(NotImplementedError):
            Namespace.from_local(f'{TMPDIR}/config.special')

        # write all test data to local files
        for ftype, data in FACTORIES.items():
            with open(f'{TMPDIR}/{ftype}.{ftype}', mode='w') as output:
                output.write(data)

        assert (Namespace(TEST_DICT) ==
                Namespace.from_local(f'{TMPDIR}/toml.toml') == Namespace.from_local(f'{TMPDIR}/tml.tml') ==
                Namespace.from_local(f'{TMPDIR}/yaml.yaml') == Namespace.from_local(f'{TMPDIR}/yml.yml') ==
                Namespace.from_local(f'{TMPDIR}/json.json'))

    def test_to_local(self) -> None:
        """Test Namespace.to_local dispatch method."""

        # test round trip
        for ftype in FACTORIES:
            ns = Namespace(TEST_DICT)
            ns.to_local(f'{TMPDIR}/{ftype}.{ftype}')
            assert ns == Namespace.from_local(f'{TMPDIR}/{ftype}.{ftype}')

        # test not implemented
        with pytest.raises(NotImplementedError):
            ns = Namespace(TEST_DICT)
            ns.to_local(f'{TMPDIR}/config.special')

    def test_attribute(self) -> None:
        """Test attribute access is the same as getitem."""
        ns = Namespace({'a': 1, 'b': 'foo', 'c': {'x': 3.14}})
        assert 1 == ns['a'] == ns.a
        assert 'foo' == ns['b'] == ns.b
        assert 3.14 == ns['c']['x'] == ns.c.x

    def test_attribute_expand_env(self) -> None:
        """Test transparent environment variable expansion."""
        os.environ['CMDKIT_TEST_A'] = 'foo-bar'
        ns = Namespace({'test_env': 'CMDKIT_TEST_A'})
        assert ns.get('test') is None
        assert ns.get('test_env') == 'CMDKIT_TEST_A'
        assert ns.test == 'foo-bar'

    def test_attribute_expand_eval(self) -> None:
        """Test transparent shell expression expansion."""
        ns = Namespace({'test_eval': 'echo foo-bar'})
        assert ns.get('test') is None
        assert ns.get('test_eval') == 'echo foo-bar'
        assert ns.test == 'foo-bar'

    def test_duplicates(self) -> None:
        """Namespace can find duplicate leaves in the tree."""
        ns = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert ns.duplicates() == {'x': [('a',), ('b',)]}

    def test_whereis(self) -> None:
        """Namespace can find paths to leaves in the tree."""
        ns = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert ns.whereis('x') == [('a',), ('b',)]
        assert ns.whereis('x', 1) == [('a',)]
        assert ns.whereis('x', lambda v: v % 3 == 0) == [('b',)]


TEST_ENV_TYPES = """\
CMDKIT_INT=1
CMDKIT_FLOAT=3.14
CMDKIT_TRUE=true
CMDKIT_FALSE=false
CMDKIT_NULL=null
CMDKIT_STR=other
"""


class TestEnviron:
    """Unit tests for Environ."""

    def test_init(self) -> None:
        """Test environment variable initialization along with Environ.reduce()."""

        # clean environment of any existing variables with the item
        prefix = 'CMDKIT'
        for var in dict(os.environ):
            if var.startswith(prefix):
                os.environ.pop(var)

        # populate environment with test variables
        for line in TEST_ENV.strip().split('\n'):
            field, value = line.strip().split('=')
            os.environ[field] = value

        # test base level Namespace|Environ equivalence
        assert Namespace.from_env(prefix=prefix) == Environ(prefix=prefix)
        assert Environ(prefix=prefix).expand() == Namespace(TEST_DICT)

    def test_expand(self) -> None:
        """Test automatic type coercion with Environ.reduce()."""

        # clean environment of any existing variables with the item
        prefix = 'CMDKIT'
        for var in dict(os.environ):
            if var.startswith(prefix):
                os.environ.pop(var)

        # populate environment with test variables
        for line in TEST_ENV_TYPES.strip().split('\n'):
            field, value = line.strip().split('=')
            os.environ[field] = value

        env = Environ(prefix=prefix).expand()
        assert isinstance(env['int'], int) and env['int'] == 1
        assert isinstance(env['float'], float) and env['float'] == 3.14
        assert isinstance(env['true'], bool) and env['true'] is True
        assert isinstance(env['false'], bool) and env['false'] is False
        assert env['null'] is None
        assert env['str'] == 'other'

    def test_flatten(self) -> None:
        """Test round-trip Environ('...').expand().flatten()."""

        # clean environment of any existing variables with the item
        prefix = 'CMDKIT'
        for var in dict(os.environ):
            if var.startswith(prefix):
                os.environ.pop(var)

        # populate environment with test variables
        for line in TEST_ENV_TYPES.strip().split('\n'):
            field, value = line.strip().split('=')
            os.environ[field] = value

        env = Namespace.from_env(prefix)
        assert env == env.expand().flatten(prefix=prefix)

    def test_defaults(self) -> None:
        """Test defaults for missing environment variables."""

        # clean environment of any existing variables with the item
        prefix = 'CMDKIT'
        for var in dict(os.environ):
            if var.startswith(prefix):
                os.environ.pop(var)

        # populate environment with test variables
        for line in TEST_ENV_TYPES.strip().split('\n'):
            field, value = line.strip().split('=')
            os.environ[field] = value

        # add default
        env = Environ(prefix=prefix, defaults={'CMDKIT_DEFAULT_VALUE': '42'}).reduce()
        value = env['default']['value']
        assert isinstance(value, int) and value == 42


CONFIG_DEFAULT = """\
[a]
var0 = "default_var0"
var1 = "default_var1"
var2 = "default_var2"
"""


CONFIG_SYSTEM = """\
[a]
var1 = "system_var1"
"""


CONFIG_USER = """\
[a]
var2 = "user_var2"

[b]
var3 = "user_var3"
"""


CONFIG_LOCAL = """\
[b]
var3 = "local_var3"

[c]
var4 = "local_var4"
"""


CONFIG_ENVIRON = """\
CMDKIT_C_VAR4=env_var4
CMDKIT_C_VAR5=env_var5
"""


CONFIG_SOURCES = {
    'system': CONFIG_SYSTEM,
    'user': CONFIG_USER,
    'local': CONFIG_LOCAL
}


class TestConfiguration:
    """Unit tests for Configuration."""

    def test_init(self) -> None:
        """Test initialization."""

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

    def test_blending(self) -> None:
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

    def test_from_local(self) -> None:
        """Test Configuration.from_local factory method."""

        # initial local files
        for label, data in CONFIG_SOURCES.items():
            with open(f'{TMPDIR}/{label}.toml', mode='w') as output:
                output.write(data)

        # clean environment of any existing variables with the item
        prefix = 'CMDKIT'
        for var in dict(os.environ):
            if var.startswith(prefix):
                os.environ.pop(var)

        # populate environment with test variables
        for line in CONFIG_ENVIRON.strip().split('\n'):
            field, value = line.strip().split('=')
            os.environ[field] = value

        # build configuration
        default = Namespace.from_toml(StringIO(CONFIG_DEFAULT))
        cfg = Configuration.from_local(default=default, env=True, prefix=prefix,
                                       system=f'{TMPDIR}/system.toml',
                                       user=f'{TMPDIR}/user.toml',
                                       local=f'{TMPDIR}/local.toml')

        # verify namespace isolation
        assert cfg.namespaces['default'] == Namespace.from_toml(StringIO(CONFIG_DEFAULT))
        assert cfg.namespaces['system'] == Namespace.from_toml(StringIO(CONFIG_SYSTEM))
        assert cfg.namespaces['user'] == Namespace.from_toml(StringIO(CONFIG_USER))
        assert cfg.namespaces['local'] == Namespace.from_toml(StringIO(CONFIG_LOCAL))
        assert cfg.namespaces['env'] == Environ(prefix).reduce()

        # verify parameter lineage
        assert cfg['a']['var0'] == 'default_var0' and cfg.which('a', 'var0') == 'default'
        assert cfg['a']['var1'] == 'system_var1' and cfg.which('a', 'var1') == 'system'
        assert cfg['a']['var2'] == 'user_var2' and cfg.which('a', 'var2') == 'user'
        assert cfg['b']['var3'] == 'local_var3' and cfg.which('b', 'var3') == 'local'
        assert cfg['c']['var4'] == 'env_var4' and cfg.which('c', 'var4') == 'env'
        assert cfg['c']['var5'] == 'env_var5' and cfg.which('c', 'var5') == 'env'

    def test_live_update(self) -> None:
        """Test direct modification of configuration data."""

        cfg = Configuration(a=Namespace(x=1))
        assert repr(cfg) == 'Configuration(a=Namespace({\'x\': 1}))'
        assert dict(cfg) == {'x': 1}
        assert cfg.which('x') == 'a'

        cfg.x = 2
        assert repr(cfg) == 'Configuration(a=Namespace({\'x\': 1}), _=Namespace({\'x\': 2}))'
        assert dict(cfg) == {'x': 2}
        assert cfg.which('x') == '_'

        cfg.update(y=2)
        assert dict(cfg) == {'x': 2, 'y': 2}
        assert repr(cfg) == 'Configuration(a=Namespace({\'x\': 1}), _=Namespace({\'x\': 2, \'y\': 2}))'
        assert cfg.which('y') == '_'

        cfg.update(y=3)
        assert dict(cfg) == {'x': 2, 'y': 3}
        assert repr(cfg) == 'Configuration(a=Namespace({\'x\': 1}), _=Namespace({\'x\': 2, \'y\': 3}))'
        assert cfg.which('y') == '_'

    def test_duplicates(self) -> None:
        """Configuration can find duplicate leaves in the trees."""

        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        cfg = Configuration(one=one, two=two)

        assert cfg.duplicates() == {'x': {'one': [('a',), ('b',)], 'two': [('b',)]},
                                    'z': {'one': [('b',)], 'two': [('b',)]}}
    
    def test_whereis(self) -> None:
        """Configuration can find paths to leaves in the tree."""

        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4}, 'c': {'j': True, 'k': 3.14}})
        cfg = Configuration(one=one, two=two)

        assert cfg.whereis('x') == {'one': [('a',), ('b',)], 'two': [('b',)]}
        assert cfg.whereis('x', 1) == {'one': [('a',)], 'two': []}
        assert cfg.whereis('x', lambda v: v % 3 == 0) == {'one': [('b',)], 'two': []}

    def test_pop(self) -> None:
        """Configuration cannot use inherited pop method."""

        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        cfg = Configuration(one=one, two=two)

        with pytest.raises(NotImplementedError):
            cfg.pop('x')

    def test_popitem(self) -> None:
        """Configuration cannot use inherited popitem method."""

        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        cfg = Configuration(one=one, two=two)

        with pytest.raises(NotImplementedError):
            cfg.popitem()
