# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for `cmdkit.config` behavior and interfaces."""


# standard libs
import io
import os
from io import StringIO
from pathlib import Path
from string import ascii_letters

# external libs
import pytest

# internal libs
from cmdkit.config import Configuration
from cmdkit.namespace import Namespace, Environ


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

    def test_factories(self, tmp_path: Path) -> None:
        """Test all implemented factory equivalents."""

        # write all test data to local files
        for ftype, data in FACTORIES.items():
            with open(f'{tmp_path}/{ftype}.{ftype}', mode='w') as output:
                output.write(data)

        # test both file-like object and file path modes of construction
        assert (Namespace(TEST_DICT) ==
                Namespace.from_toml(StringIO(TEST_TOML)) == Namespace.from_toml(f'{tmp_path}/toml.toml') ==
                Namespace.from_yaml(StringIO(TEST_YAML)) == Namespace.from_yaml(f'{tmp_path}/yaml.yaml') ==
                Namespace.from_json(StringIO(TEST_JSON)) == Namespace.from_json(f'{tmp_path}/json.json'))

    def test_from_local(self, tmp_path: Path) -> None:
        """Test automatic file type deduction and allow for missing files."""

        # clear existing files
        for ftype in FACTORIES:
            filepath = f'{tmp_path}/{ftype}.{ftype}'
            if os.path.exists(filepath):
                os.remove(filepath)
            filepath = f'{tmp_path}/{ftype}.conf'
            if os.path.exists(filepath):
                os.remove(filepath)

        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{tmp_path}/toml.toml')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{tmp_path}/toml.conf', ftype='toml')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{tmp_path}/yaml.yaml')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{tmp_path}/yaml.conf', ftype='yaml')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{tmp_path}/json.json')
        with pytest.raises(FileNotFoundError):
            Namespace.from_local(f'{tmp_path}/json.conf', ftype='json')

        assert (Namespace() ==
                Namespace.from_local(f'{tmp_path}/toml.toml', ignore_if_missing=True) ==
                Namespace.from_local(f'{tmp_path}/toml.conf', ftype='toml', ignore_if_missing=True) ==
                Namespace.from_local(f'{tmp_path}/yaml.yaml', ignore_if_missing=True) ==
                Namespace.from_local(f'{tmp_path}/yaml.conf', ftype='yaml', ignore_if_missing=True) ==
                Namespace.from_local(f'{tmp_path}/json.json', ignore_if_missing=True) ==
                Namespace.from_local(f'{tmp_path}/json.conf', ftype='json', ignore_if_missing=True))

        with pytest.raises(NotImplementedError):
            Namespace.from_local(f'{tmp_path}/config.special')

        # write all test data to local files
        for ftype, data in FACTORIES.items():
            with open(f'{tmp_path}/{ftype}.{ftype}', mode='w') as output:
                output.write(data)
            with open(f'{tmp_path}/{ftype}.conf', mode='w') as output:
                output.write(data)

        assert (Namespace(TEST_DICT) ==
                Namespace.from_local(f'{tmp_path}/toml.toml') ==
                Namespace.from_local(f'{tmp_path}/tml.tml') ==
                Namespace.from_local(f'{tmp_path}/toml.conf', ftype='toml') ==
                Namespace.from_local(f'{tmp_path}/yaml.yaml') ==
                Namespace.from_local(f'{tmp_path}/yml.yml') ==
                Namespace.from_local(f'{tmp_path}/yaml.conf', ftype='yaml') ==
                Namespace.from_local(f'{tmp_path}/json.json') ==
                Namespace.from_local(f'{tmp_path}/json.conf', ftype='json'))

    def test_to_local(self, tmp_path: Path) -> None:
        """Test Namespace.to_local dispatch method."""

        # test round trip
        for ftype in FACTORIES:
            ns = Namespace(TEST_DICT)
            ns.to_local(f'{tmp_path}/{ftype}.{ftype}')
            ns.to_local(f'{tmp_path}/{ftype}.conf', ftype=ftype)
            assert (ns ==
                    Namespace.from_local(f'{tmp_path}/{ftype}.{ftype}') ==
                    Namespace.from_local(f'{tmp_path}/{ftype}.conf', ftype=ftype))

        # test not implemented
        with pytest.raises(NotImplementedError):
            ns = Namespace(TEST_DICT)
            ns.to_local(f'{tmp_path}/config.special')

    def test_attribute(self) -> None:
        """Test attribute access is the same as getitem."""
        ns = Namespace({'a': 1, 'b': 'foo', 'c': {'x': 3.14}})
        assert 1 == ns['a'] == ns.a
        assert 'foo' == ns['b'] == ns.b
        assert 3.14 == ns['c']['x'] == ns.c.x

    def test_attribute_missing(self) -> None:
        """Test raises AttributeError if item is missing."""
        ns = Namespace({'a': 1, 'b': 'foo', 'c': {'x': 3.14}})
        with pytest.raises(AttributeError) as exc_info:
            assert ns.d == 42
        exc_info.match('\'d\' not found')

    def test_attribute_expand_env(self) -> None:
        """Test transparent environment variable expansion."""
        os.environ['CMDKIT_TEST_A'] = 'foo-bar'
        ns = Namespace({'test_env': 'CMDKIT_TEST_A'})
        assert ns.get('test') is None
        assert ns.get('test_env') == 'CMDKIT_TEST_A'
        assert ns.test_env == 'CMDKIT_TEST_A'
        assert ns.test == 'foo-bar'

    def test_attribute_expand_eval(self) -> None:
        """Test transparent shell expression expansion."""
        ns = Namespace({'test_eval': 'echo foo-bar'})
        assert ns.get('test') is None
        assert ns.get('test_eval') == 'echo foo-bar'
        assert ns.test_eval == 'echo foo-bar'
        assert ns.test == 'foo-bar'

    def test_attribute_expand_multiple_variants(self) -> None:
        """Test failure to expand because item has multiple variants."""
        ns = Namespace({'a': 1, 'test': 'foo', 'test_eval': 'echo bar'})
        with pytest.raises(AttributeError) as exc_info:
            assert ns.test == 'foo'
        assert exc_info.match('\'test\' has more than one variant')

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

    def test_attribute_missing(self) -> None:
        """Test raises AttributeError if item is missing"""
        cfg = Configuration(a=Namespace({'a': 1, 'b': 'foo', 'c': {'x': 3.14}}))
        with pytest.raises(AttributeError) as exc_info:
            assert cfg.d == 42
        exc_info.match('\'d\' not found')

    def test_attribute_expand_env(self) -> None:
        """Test transparent environment variable expansion."""
        os.environ['CMDKIT_TEST_A'] = 'foo-bar'
        cfg = Configuration(a=Namespace({'nested': {'test_env': 'CMDKIT_TEST_A'}}))
        assert cfg.nested.get('test') is None
        assert cfg.nested.get('test_env') == 'CMDKIT_TEST_A'
        assert cfg.nested.test_env == 'CMDKIT_TEST_A'
        assert cfg.nested.test == 'foo-bar'

    def test_attribute_expand_eval(self) -> None:
        """Test transparent shell expression expansion."""
        cfg = Configuration(a=Namespace({'nested': {'test_eval': 'echo foo-bar'}}))
        assert cfg.nested.get('test') is None
        assert cfg.nested.get('test_eval') == 'echo foo-bar'
        assert cfg.nested.test_eval == 'echo foo-bar'
        assert cfg.nested.test == 'foo-bar'

    def test_attribute_expand_multiple_variants(self) -> None:
        """Variants of one name from different layers: the higher layer decides."""
        cfg = Configuration(a=Namespace({'nested': {'test': 'foo', 'a': 1}}),
                            b=Namespace({'nested': {'test_eval': 'echo bar', 'b': 2}}),
                            c=Namespace({'other': {'secret_eval': 'echo baz'}}))
        assert cfg.nested.a == 1
        assert cfg.nested.b == 2
        assert cfg.other.secret == 'baz'
        assert cfg.nested.test == 'bar'

    def test_from_local(self, tmp_path: Path) -> None:
        """Test Configuration.from_local factory method."""

        # initial local files
        for label, data in CONFIG_SOURCES.items():
            with open(f'{tmp_path}/{label}.toml', mode='w') as output:
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
                                       system=f'{tmp_path}/system.toml',
                                       user=f'{tmp_path}/user.toml',
                                       local=f'{tmp_path}/local.toml')

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

        assert cfg.duplicates() == {'x': {'one': [('a',), ('b',)], 'two': [('b',)], '_': []},
                                    'z': {'one': [('b',)], 'two': [('b',)], '_': []}}

    def test_whereis(self) -> None:
        """Configuration can find paths to leaves in the tree."""

        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4}, 'c': {'j': True, 'k': 3.14}})
        cfg = Configuration(one=one, two=two)

        assert cfg.whereis('x') == {'one': [('a',), ('b',)], 'two': [('b',)], '_': []}
        assert cfg.whereis('x', 1) == {'one': [('a',)], 'two': [], '_': []}
        assert cfg.whereis('x', lambda v: v % 3 == 0) == {'one': [('b',)], 'two': [], '_': []}

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


# a value and its variants, for the collision tests: the value as stored, and as expanded
VARIANT_VALUES = {
    'token': ('plain-value', 'plain-value'),
    'token_env': ('CMDKIT_TEST_TOKEN', 'env-value'),
    'token_eval': ('echo eval-value', 'eval-value'),
}
VARIANT_PAIRS = [
    ('token', 'token_env'), ('token', 'token_eval'),
    ('token_env', 'token'), ('token_env', 'token_eval'),
    ('token_eval', 'token'), ('token_eval', 'token_env'),
]


class TestVariantCollision:
    """A value and its `_env` and `_eval` variants are one key across the layers of a Configuration."""

    @pytest.mark.parametrize('low, high', VARIANT_PAIRS, ids=[f'{a}-{b}' for a, b in VARIANT_PAIRS])
    def test_pairs(self, low: str, high: str, monkeypatch: pytest.MonkeyPatch) -> None:
        """The higher layer's variant is the only one left, and every way of reading it agrees."""
        monkeypatch.setenv('CMDKIT_TEST_TOKEN', 'env-value')
        lower = {'section': {low: VARIANT_VALUES[low][0], 'other': 1}}
        upper = {'section': {high: VARIANT_VALUES[high][0], 'more': 2}}
        cfg = Configuration(lower=Namespace(lower), upper=Namespace(upper))

        assert dict(cfg) == {'section': {'other': 1, high: VARIANT_VALUES[high][0], 'more': 2}}
        assert list(cfg['section']) == ['other', high, 'more']
        assert cfg.section.token == VARIANT_VALUES[high][1]
        assert cfg['section'][high] == VARIANT_VALUES[high][0]
        with pytest.raises(KeyError):
            cfg['section'][low]
        assert cfg.which('section', high) == 'upper'
        with pytest.raises(KeyError):
            cfg.which('section', low)
        assert cfg.which('section', 'other') == 'lower'
        assert cfg.which('section', 'more') == 'upper'
        assert cfg.which('section') == 'upper'
        assert cfg.namespaces['lower'] == lower
        assert cfg.namespaces['upper'] == upper

    def test_top_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The rule holds for parameters at the top level."""
        monkeypatch.setenv('CMDKIT_TEST_TOKEN', 'env-value')
        cfg = Configuration(lower=Namespace({'token': 'a', 'x': 1}),
                            upper=Namespace({'token_env': 'CMDKIT_TEST_TOKEN'}))
        assert dict(cfg) == {'x': 1, 'token_env': 'CMDKIT_TEST_TOKEN'}
        assert cfg.token == 'env-value'
        assert 'token' not in cfg
        with pytest.raises(KeyError):
            cfg['token']
        assert cfg.which('token_env') == 'upper'
        assert cfg.which('x') == 'lower'
        with pytest.raises(KeyError):
            cfg.which('token')
        assert cfg.namespaces['lower'] == {'token': 'a', 'x': 1}

    def test_deep(self) -> None:
        """The rule holds three levels down, beside keys the merge keeps."""
        lower = {'a': {'b': {'c': {'token_eval': 'echo low', 'keep': 1}, 'also': 2}}}
        upper = {'a': {'b': {'c': {'token': 'high'}}}}
        cfg = Configuration(lower=Namespace(lower), upper=Namespace(upper))
        assert dict(cfg) == {'a': {'b': {'c': {'keep': 1, 'token': 'high'}, 'also': 2}}}
        assert cfg.a.b.c.token == 'high'
        assert cfg['a']['b']['c']['token'] == 'high'
        with pytest.raises(KeyError):
            cfg['a']['b']['c']['token_eval']
        assert cfg.which('a', 'b', 'c', 'token') == 'upper'
        assert cfg.which('a', 'b', 'c', 'keep') == 'lower'
        assert cfg.which('a', 'b', 'also') == 'lower'
        with pytest.raises(KeyError):
            cfg.which('a', 'b', 'c', 'token_eval')
        assert cfg.namespaces['lower'] == lower
        assert cfg.namespaces['upper'] == upper

    def test_suffix_alone(self) -> None:
        """A key ending in `_env` is a variant by its suffix, whatever was meant by it."""
        cfg = Configuration(lower=Namespace({'conda': 'x'}),
                            upper=Namespace({'conda_env': 'base'}))
        assert dict(cfg) == {'conda_env': 'base'}
        assert cfg['conda_env'] == 'base'
        with pytest.raises(KeyError):
            cfg['conda']
        with pytest.raises(KeyError):
            cfg.which('conda')
        assert cfg.which('conda_env') == 'upper'

    def test_mapping_values(self) -> None:
        """Mappings displace and are displaced like any value, and a name set again still merges."""
        # a mapping displaced by a scalar variant
        cfg = Configuration(lower=Namespace({'s': {'token': {'a': 1}, 'k': 0}}),
                            upper=Namespace({'s': {'token_env': 'VAR'}}))
        assert dict(cfg) == {'s': {'k': 0, 'token_env': 'VAR'}}
        with pytest.raises(KeyError):
            cfg.which('s', 'token', 'a')
        with pytest.raises(KeyError):
            cfg.which('s', 'token')
        assert cfg.which('s', 'token_env') == 'upper'

        # a scalar variant displaced by a mapping
        cfg = Configuration(lower=Namespace({'s': {'token_env': 'VAR'}}),
                            upper=Namespace({'s': {'token': {'a': 1}}}))
        assert dict(cfg) == {'s': {'token': {'a': 1}}}
        assert cfg.s.token.a == 1
        assert cfg.which('s', 'token', 'a') == 'upper'
        with pytest.raises(KeyError):
            cfg.which('s', 'token_env')

        # a mapping-valued name set again beside another variant merges depth-first
        cfg = Configuration(lower=Namespace({'s': {'token': {'a': 1}}}),
                            upper=Namespace({'s': {'token': {'b': 2}, 'token_env': 'VAR'}}))
        assert dict(cfg) == {'s': {'token': {'a': 1, 'b': 2}, 'token_env': 'VAR'}}
        assert cfg.which('s', 'token', 'a') == 'lower'
        assert cfg.which('s', 'token', 'b') == 'upper'
        assert cfg.which('s', 'token_env') == 'upper'
        with pytest.raises(AttributeError, match='\'token\' has more than one variant'):
            cfg.s.token

        # a mapping-valued variant displaced by another mapping-valued variant
        cfg = Configuration(lower=Namespace({'s': {'token_eval': {'a': 1}}}),
                            upper=Namespace({'s': {'token': {'b': 2}}}))
        assert dict(cfg) == {'s': {'token': {'b': 2}}}
        with pytest.raises(KeyError):
            cfg.which('s', 'token_eval', 'a')
        assert cfg.namespaces['lower'] == {'s': {'token_eval': {'a': 1}}}

    def test_deciding_layer_ambiguous(self) -> None:
        """The deciding layer's own two variants are both kept, and attribute access raises."""
        cfg = Configuration(lower=Namespace({'s': {'token_eval': 'echo low'}}),
                            upper=Namespace({'s': {'token': 'a', 'token_env': 'VAR'}}))
        assert dict(cfg) == {'s': {'token': 'a', 'token_env': 'VAR'}}
        assert 'token_eval' not in cfg['s']
        with pytest.raises(AttributeError, match='\'token\' has more than one variant'):
            cfg.s.token
        assert cfg.which('s', 'token') == 'upper'
        assert cfg.which('s', 'token_env') == 'upper'
        with pytest.raises(KeyError):
            cfg.which('s', 'token_eval')

    def test_namespace_update_unchanged(self) -> None:
        """A plain Namespace keeps both variants on update, and attribute access raises."""
        ns = Namespace({'s': {'token': 'a'}})
        ns.update({'s': {'token_env': 'VAR'}})
        assert ns == {'s': {'token': 'a', 'token_env': 'VAR'}}
        with pytest.raises(AttributeError, match='\'token\' has more than one variant'):
            ns.s.token

    def test_no_expansion(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Building, merging and reading by item never run a command or read a variable."""
        calls = []

        def getenv(name, default=None):
            calls.append(name)
            return f'read-{name}'

        monkeypatch.setattr(os, 'getenv', getenv)
        marker, other = tmp_path / 'ran', tmp_path / 'ran-other'
        one = {'s': {'token_eval': f'touch {marker}', 'x_env': 'X_VAR', 'y_eval': f'touch {other}'}}
        two = {'s': {'token_env': 'TOKEN_VAR', 'x_eval': f'touch {marker}'}}
        three = {'s': {'x': 'plain', 'token_eval': f'touch {marker}', 'token_env': 'TOKEN_VAR'}}
        cfg = Configuration(one=Namespace(one), two=Namespace(two))
        cfg.extend(three=Namespace(three))
        assert dict(cfg) == {'s': {'y_eval': f'touch {other}', 'x': 'plain',
                                   'token_eval': f'touch {marker}', 'token_env': 'TOKEN_VAR'}}
        assert 'Configuration(one=' in repr(cfg)
        assert cfg['s']['x'] == 'plain'
        assert cfg['s']['token_eval'] == f'touch {marker}'
        assert cfg.which('s', 'x') == 'three'
        assert cfg.which('s', 'y_eval') == 'one'
        with pytest.raises(KeyError):
            cfg.which('s', 'x_env')
        assert cfg.namespaces['one'] == one
        assert cfg.namespaces['two'] == two
        assert cfg.namespaces['three'] == three
        assert calls == []
        assert not marker.exists() and not other.exists()

        # attribute access does expand: the probes above could have seen it
        assert cfg.s.x == 'plain'
        assert cfg.s.y == ''
        assert other.exists() and not marker.exists()
        with pytest.raises(AttributeError, match='\'token\' has more than one variant'):
            cfg.s.token
        assert Configuration(one=Namespace(one)).s.x == 'read-X_VAR'
        assert calls == ['X_VAR']

    def test_non_string_keys(self) -> None:
        """Keys that are not strings have no variants, and merge as they always have."""
        cfg = Configuration(lower=Namespace({1: 'a', 's': {2: 'b', 'k': 0}}),
                            upper=Namespace({'1_env': 'VAR', 's': {2: 'c'}}))
        assert dict(cfg) == {1: 'a', 's': {2: 'c', 'k': 0}, '1_env': 'VAR'}
        assert cfg.which(1) == 'lower'
        assert cfg.which('1_env') == 'upper'
        assert cfg.which('s', 2) == 'upper'
        with pytest.raises(KeyError):
            cfg.which('s', 3)

        cfg = Configuration(lower=Namespace({'1': 'a', 1: 'b'}),
                            upper=Namespace({'1_eval': 'echo c', 1: 'd'}))
        assert dict(cfg) == {1: 'd', '1_eval': 'echo c'}
        assert cfg.which(1) == 'upper'
        with pytest.raises(KeyError):
            cfg.which('1')

    def test_double_suffix(self) -> None:
        """A key ending in `_env` is a variant of two names: the highest layer still decides."""
        cfg = Configuration(one=Namespace({'token': 'a'}),
                            two=Namespace({'token_env': 'VAR'}),
                            three=Namespace({'token_env_eval': 'echo b'}))
        assert dict(cfg) == {'token_env_eval': 'echo b'}
        assert cfg.which('token_env_eval') == 'three'
        with pytest.raises(KeyError):
            cfg.which('token')
        with pytest.raises(KeyError):
            cfg.which('token_env')
        with pytest.raises(AttributeError, match='\'token\' not found'):
            cfg.token
        assert cfg.token_env == 'b'

        # and the other way around: a plain suffixed key displaces its own variants
        cfg = Configuration(one=Namespace({'token_env_eval': 'echo b'}),
                            two=Namespace({'token_env': 'VAR'}))
        assert dict(cfg) == {'token_env': 'VAR'}
        with pytest.raises(KeyError):
            cfg.which('token_env_eval')

    def test_extend_and_from_local(self, tmp_path: Path) -> None:
        """Layers added after construction, and files loaded by from_local, follow the rule."""
        cfg = Configuration(lower=Namespace({'s': {'token': 'a', 'k': 1}}))
        cfg.extend(upper=Namespace({'s': {'token_eval': 'echo b'}}))
        assert dict(cfg) == {'s': {'k': 1, 'token_eval': 'echo b'}}
        assert cfg['s']['token_eval'] == 'echo b'
        with pytest.raises(KeyError):
            cfg['s']['token']
        assert cfg.which('s', 'token_eval') == 'upper'
        with pytest.raises(KeyError):
            cfg.which('s', 'token')

        first, second = tmp_path / 'first.toml', tmp_path / 'second.toml'
        first.write_text('[server]\nauth = "secret"\nport = 1234\n')
        second.write_text('[server]\nauth_eval = "echo from-command"\n')
        cfg = Configuration.from_local(first=str(first), second=str(second))
        assert dict(cfg) == {'server': {'port': 1234, 'auth_eval': 'echo from-command'}}
        assert cfg.server.auth == 'from-command'
        assert cfg.server.port == 1234
        assert cfg.which('server', 'auth_eval') == 'second'
        with pytest.raises(KeyError):
            cfg.which('server', 'auth')
        assert cfg.which('server', 'port') == 'first'
        assert cfg.namespaces['first'] == {'server': {'auth': 'secret', 'port': 1234}}

    def test_which_unchanged(self) -> None:
        """Where no variant is displaced, which answers as it always has."""
        # through a higher scalar, both orders
        cfg = Configuration(lower=Namespace({'x': {'y': 1}}), upper=Namespace({'x': 5}))
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('x', 'y')
        cfg = Configuration(lower=Namespace({'x': 5}), upper=Namespace({'x': {'z': 1}}))
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('x', 'y')

        # a nested mapping names the highest layer
        cfg = Configuration(lower=Namespace({'a': {'x': 1}}), upper=Namespace({'a': {'y': 2}}))
        assert cfg.which('a') == 'upper'
        assert cfg.which('a', 'x') == 'lower'

        # a missing key, and a bare name whose only variant is suffixed
        cfg = Configuration(one=Namespace({'token_env': 'VAR', 'a': {'b': 1}}))
        with pytest.raises(KeyError):
            cfg.which('nope')
        with pytest.raises(KeyError):
            cfg.which('a', 'nope')
        with pytest.raises(KeyError):
            cfg.which('token')
        assert cfg.which('token_env') == 'one'

    def test_which_restored(self) -> None:
        """A variant displaced and then set again higher up is named by the layer that set it."""
        cfg = Configuration(one=Namespace({'token': 'a', 's': {'token': 'a'}}),
                            two=Namespace({'token_env': 'VAR', 's': {'token_env': 'VAR'}}),
                            three=Namespace({'token': 'c', 's': {'token': 'c'}}))
        assert dict(cfg) == {'token': 'c', 's': {'token': 'c'}}
        assert cfg.which('token') == 'three'
        assert cfg.which('s', 'token') == 'three'
        with pytest.raises(KeyError):
            cfg.which('token_env')
        with pytest.raises(KeyError):
            cfg.which('s', 'token_env')

    def test_which_displaced_through_scalar(self) -> None:
        """A variant displaced above an intervening scalar is gone for item access and which."""
        cfg = Configuration(one=Namespace({'x': {'y': 1}}),
                            two=Namespace({'x': 5}),
                            three=Namespace({'x': {'y_env': 'VAR'}}))
        assert dict(cfg) == {'x': {'y_env': 'VAR'}}
        with pytest.raises(KeyError):
            cfg['x']['y']
        with pytest.raises(KeyError):
            cfg.which('x', 'y')
        assert cfg.which('x', 'y_env') == 'three'

    def test_which_through_scalars(self) -> None:
        """A path through a scalar still raises TypeError, beside and beneath displaced variants."""
        # a layer without x beside x.y, x = 5, x.z
        cfg = Configuration(zero=Namespace({'w': 0}),
                            one=Namespace({'x': {'y': 1}}),
                            two=Namespace({'x': 5}),
                            three=Namespace({'x': {'z': 1}}))
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('x', 'y')

        # x.y and x.y_env under a higher x = 5
        cfg = Configuration(one=Namespace({'x': {'y': 1}}),
                            two=Namespace({'x': {'y_env': 'VAR'}}),
                            three=Namespace({'x': 5}))
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('x', 'y')
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('x', 'y_env')

        # a deciding layer holding token and token_env beneath a scalar and a fresh mapping
        cfg = Configuration(zero=Namespace({'s': {'token': 'z'}}),
                            one=Namespace({'s': {'token': 'a', 'token_env': 'VAR'}}),
                            two=Namespace({'s': 5}),
                            three=Namespace({'s': {'other': 1}}))
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('s', 'token')
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('s', 'token_env')

    def test_which_displaced_scalar_prefix(self) -> None:
        """A path through a scalar a higher variant displaced is gone for which, as for item access."""
        # a top-level scalar displaced by its variant
        cfg = Configuration(lower=Namespace({'u': 0}), upper=Namespace({'u_env': 'VAR'}))
        with pytest.raises(KeyError):
            cfg['u']
        with pytest.raises(KeyError):
            cfg.which('u', 't')
        with pytest.raises(KeyError):
            cfg.which('u', 't', 'v')
        with pytest.raises(KeyError):
            cfg.which('u')
        assert cfg.which('u_env') == 'upper'

        # a nested scalar displaced by its variant
        cfg = Configuration(lower=Namespace({'s': {'token': 5}}), upper=Namespace({'s': {'token_env': 'VAR'}}))
        with pytest.raises(KeyError):
            cfg['s']['token']
        with pytest.raises(KeyError):
            cfg.which('s', 'token', 'a')
        assert cfg.which('s', 'token_env') == 'upper'

        # no displacement on the path: through the merged view's scalar, both raise TypeError
        cfg = Configuration(base=Namespace({'w': 0}), zero=Namespace({'u_env': 'VAR'}),
                            one=Namespace({'u': 5}))
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg['u']['t']
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('u', 't')

        # nor beneath a scalar a fresh mapping replaced: which keeps its TypeError
        cfg.extend(two=Namespace({'u': {}}))
        with pytest.raises(KeyError):
            cfg['u']['t']
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('u', 't')

    def test_which_scalar_below_fresh_variant(self) -> None:
        """A variant beneath a key whose lower value was a scalar displaces nothing: TypeError stays."""
        cfg = Configuration(l1=Namespace({'s': {'t': 5}}), l2=Namespace({'s': {'t': {'x_env': 1}}}))
        assert dict(cfg) == {'s': {'t': {'x_env': 1}}}
        with pytest.raises(KeyError):
            cfg['s']['t']['x']
        with pytest.raises(TypeError, match='not subscriptable'):
            cfg.which('s', 't', 'x')
        assert cfg.which('s', 't', 'x_env') == 'l2'

    def test_update(self) -> None:
        """An in-place update replaces a layer's different variant, in `_` and in the merged view."""
        layer = {'s': {'token': 'a', 'k': 1}}
        cfg = Configuration(base=Namespace(layer))
        cfg.update({'s': {'token_eval': 'echo b'}})
        assert cfg.local == {'s': {'token_eval': 'echo b'}}
        assert dict(cfg) == {'s': {'k': 1, 'token_eval': 'echo b'}}
        assert cfg.s.token == 'b'
        assert cfg['s']['token_eval'] == 'echo b'
        with pytest.raises(KeyError):
            cfg['s']['token']
        assert cfg.which('s', 'token_eval') == '_'
        assert cfg.which('s', 'k') == 'base'
        with pytest.raises(KeyError):
            cfg.which('s', 'token')
        assert cfg.namespaces['base'] == layer

    def test_successive_updates(self) -> None:
        """A later in-place variant replaces an earlier one, so `_` never holds both."""
        cfg = Configuration(base=Namespace({'x': 1}))
        cfg.update(token='a')
        cfg.update(token_env='VAR')
        assert cfg.local == {'token_env': 'VAR'}
        assert dict(cfg) == {'x': 1, 'token_env': 'VAR'}
        assert cfg.which('token_env') == '_'
        with pytest.raises(KeyError):
            cfg.which('token')

        cfg.update({'s': {'token_eval': 'echo a'}})
        cfg.update({'s': {'token': 'b'}})
        assert cfg.local == {'token_env': 'VAR', 's': {'token': 'b'}}
        assert cfg.s.token == 'b'
        assert cfg.which('s', 'token') == '_'
        assert cfg.namespaces['base'] == {'x': 1}

    def test_attribute_assignment(self) -> None:
        """Assigning a name whose variant is in the merged view is an in-place change."""
        # from one layer
        cfg = Configuration(one=Namespace({'token_env': 'VAR'}))
        cfg.token = 'v'
        assert cfg.local == {'token': 'v'}
        assert dict(cfg) == {'token': 'v'}
        assert 'token' not in vars(cfg)
        assert cfg.token == 'v'
        assert cfg.which('token') == '_'
        with pytest.raises(KeyError):
            cfg.which('token_env')
        assert cfg.namespaces['one'] == {'token_env': 'VAR'}

        # from a collision of two layers
        cfg = Configuration(one=Namespace({'token': 'a'}), two=Namespace({'token_env': 'VAR'}))
        cfg.token = 'v'
        assert cfg.local == {'token': 'v'}
        assert dict(cfg) == {'token': 'v'}
        assert 'token' not in vars(cfg)
        assert cfg.which('token') == '_'

        # a suffixed name over the merged view's plain one
        cfg.token_env = 'OTHER'
        assert cfg.local == {'token_env': 'OTHER'}
        assert dict(cfg) == {'token_env': 'OTHER'}
        assert 'token_env' not in vars(cfg)
        assert cfg.which('token_env') == '_'
        with pytest.raises(KeyError):
            cfg.which('token')
        assert cfg.namespaces['one'] == {'token': 'a'}
        assert cfg.namespaces['two'] == {'token_env': 'VAR'}

    def test_attribute_assignment_unchanged(self) -> None:
        """A name with no variant in the merged view is an attribute; a present name goes to `_`."""
        cfg = Configuration(one=Namespace({'x': 1}))
        cfg.y = 2
        assert vars(cfg)['y'] == 2
        assert 'y' not in cfg
        assert cfg.local == {}
        assert dict(cfg) == {'x': 1}

        cfg.x = 3
        assert 'x' not in vars(cfg)
        assert cfg.local == {'x': 3}
        assert dict(cfg) == {'x': 3}
        assert cfg.which('x') == '_'


class TestFileLoading:
    """Loading and writing files by path or handle, and how from_local and to_local dispatch."""

    @pytest.mark.parametrize('ext', ['toml', 'tml', 'yaml', 'yml', 'json'])
    def test_path_round_trip(self, tmp_path: Path, ext: str) -> None:
        """A pathlib.Path or a bare os.PathLike reads and writes as a str path does."""

        class Bare:
            """Nothing but the os.PathLike protocol."""
            def __init__(self, path: str) -> None:
                self.path = path
            def __fspath__(self) -> str:
                return self.path

        ns = Namespace(TEST_DICT)
        reference = tmp_path / f'reference.{ext}'
        ns.to_local(str(reference))
        expected = reference.read_bytes()
        for name, make in [('path', Path), ('bare', lambda p: Bare(str(p)))]:
            by_ext, by_ftype, direct = (tmp_path / f'{name}-ext.{ext}', tmp_path / f'{name}-ftype.conf',
                                        tmp_path / f'{name}-direct.{ext}')
            assert isinstance(make(by_ext), os.PathLike) and not isinstance(make(by_ext), str)
            assert ns.to_local(make(by_ext)) is None
            assert ns.to_local(make(by_ftype), ftype=ext) is None
            assert getattr(ns, f'to_{ext}')(make(direct)) is None
            for written in (by_ext, by_ftype, direct):
                assert written.read_bytes() == expected
            loaded = [Namespace.from_local(make(by_ext)),
                      Namespace.from_local(make(by_ftype), ftype=ext),
                      getattr(Namespace, f'from_{ext}')(make(direct))]
            for each in loaded:
                assert type(each) is Namespace
                assert each == ns == TEST_DICT

    def test_path_ignore_if_missing(self, tmp_path: Path) -> None:
        """A missing pathlib.Path is empty when allowed, by extension or by ftype, and an error otherwise."""
        for ext in ['toml', 'tml', 'yaml', 'yml', 'json', 'ini']:
            ns = Namespace.from_local(tmp_path / f'missing.{ext}', ignore_if_missing=True)
            assert type(ns) is Namespace and ns == {}
        for ext in ['toml', 'tml', 'yaml', 'yml', 'json']:
            ns = Namespace.from_local(tmp_path / 'missing.conf', ftype=ext, ignore_if_missing=True)
            assert type(ns) is Namespace and ns == {}
            with pytest.raises(FileNotFoundError):
                Namespace.from_local(tmp_path / f'missing.{ext}')
            with pytest.raises(FileNotFoundError):
                Namespace.from_local(tmp_path / 'missing.conf', ftype=ext)

    def test_configuration_path_layers(self, tmp_path: Path) -> None:
        """Configuration.from_local takes pathlib.Path layers, a missing one empty."""
        system, user, local = tmp_path / 'system.toml', tmp_path / 'user.yaml', tmp_path / 'local.json'
        system.write_text('[a]\nx = 1\ny = 2\n\n[b]\nz = 3\n')
        user.write_text('a:\n  x: 4\n')
        cfg = Configuration.from_local(system=system, user=user, local=local)
        assert dict(cfg) == {'a': {'x': 4, 'y': 2}, 'b': {'z': 3}}
        assert cfg.which('a', 'x') == 'user'
        assert cfg.which('a', 'y') == 'system'
        assert cfg.which('b', 'z') == 'system'
        assert cfg.namespaces['system'] == {'a': {'x': 1, 'y': 2}, 'b': {'z': 3}}
        assert cfg.namespaces['user'] == {'a': {'x': 4}}
        assert cfg.namespaces['local'] == {}

    def test_loader_error_propagates(self, tmp_path: Path) -> None:
        """An exception raised by the loader comes out of from_local as itself."""
        path = tmp_path / 'c.json'
        path.write_text('{"a": 1}')
        for error in (AttributeError('inner'), KeyError('k')):

            class Failing(Namespace):
                @classmethod
                def from_json(cls, path_or_file, **options) -> Namespace:
                    raise error

            for given in (str(path), path):
                with pytest.raises(type(error)) as info:
                    Failing.from_local(given)
                assert info.value is error
                with pytest.raises(type(error)) as info:
                    Failing.from_local(given, ftype='json')
                assert info.value is error

    def test_writer_error_propagates(self, tmp_path: Path) -> None:
        """An exception raised by the writer comes out of to_local as itself."""
        path = tmp_path / 'c.json'
        for error in (AttributeError('inner'), KeyError('k')):

            class Failing(Namespace):
                def to_json(self, path_or_file, **options) -> None:
                    raise error

            for given in (str(path), path):
                with pytest.raises(type(error)) as info:
                    Failing({'a': 1}).to_local(given)
                assert info.value is error
                with pytest.raises(type(error)) as info:
                    Failing({'a': 1}).to_local(given, ftype='json')
                assert info.value is error
        assert not path.exists()

    def test_unsupported_extension(self, tmp_path: Path) -> None:
        """An extension with no file loader or writer names the class and the extension."""

        class Custom(Namespace):
            """A subclass adding nothing."""

        marker = tmp_path / 'ran'
        for ext in ['ini', 'dict', 'env', 'local']:
            present = tmp_path / f'present.{ext}'
            present.write_text('a = 1\n')
            for cls in (Namespace, Custom):
                for given in (str(present), present):
                    with pytest.raises(NotImplementedError) as info:
                        cls.from_local(given)
                    assert info.value.args == (f'{cls.__name__} does not currently support \'{ext}\' files', )
                    with pytest.raises(NotImplementedError) as info:
                        cls.from_local(given, ignore_if_missing=True)
                    assert info.value.args == (f'{cls.__name__} does not currently support \'{ext}\' files', )
                target = tmp_path / f'target.{ext}'
                for ns in (cls({'a': 1}), cls({f'to_{ext}': 5}), cls({f'to_{ext}_eval': f'touch {marker}'})):
                    for given in (str(target), target):
                        with pytest.raises(NotImplementedError) as info:
                            ns.to_local(given)
                        assert info.value.args == (f'{cls.__name__} does not currently support "{ext}" files', )
                assert not target.exists()
        assert not marker.exists()

    def test_toml_binary_handle(self, tmp_path: Path) -> None:
        """from_toml reads a binary handle as it reads a text handle."""
        path = tmp_path / 'c.toml'
        path.write_text(TEST_TOML)
        with open(path, mode='rb') as stream:
            from_binary = Namespace.from_toml(stream)
        with open(path) as stream:
            from_text = Namespace.from_toml(stream)
        from_bytes = Namespace.from_toml(io.BytesIO(TEST_TOML.encode()))
        for ns in (from_binary, from_text, from_bytes):
            assert type(ns) is Namespace
            assert ns == TEST_DICT

    def test_toml_text_handle(self, tmp_path: Path) -> None:
        """to_toml writes a text handle as it writes a binary handle or a path."""
        ns = Namespace({'a': {'x': 1, 'y': 'caf\u00e9'}, 'b': [1, 2]})
        path = tmp_path / 'path.toml'
        ns.to_toml(path)
        expected = path.read_bytes()
        assert expected
        text, binary = io.StringIO(), io.BytesIO()
        assert ns.to_toml(text) is None
        assert ns.to_toml(binary) is None
        handle = tmp_path / 'handle.toml'
        with open(handle, mode='w', encoding='utf-8') as stream:
            assert ns.to_toml(stream) is None
        assert text.getvalue().encode() == binary.getvalue() == handle.read_bytes() == expected
        assert Namespace.from_toml(io.StringIO(text.getvalue())) == ns
        assert Namespace.from_toml(handle) == ns
