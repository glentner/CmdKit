# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Unit tests for `cmdkit.config.builder` behavior and interfaces."""

# internal libs
from cmdkit.config import Namespace
from cmdkit.contrib.builder import BuilderNamespace, BuilderConfiguration


class TestBuilderNamespace:
    """Unit tests for BuilderNamespace."""

    def test_repr(self) -> None:
        """Visual representation of BuilderNamespace."""
        ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert repr(ns) == 'BuilderNamespace({\'a\': {\'x\': 1, \'y\': 2}, \'b\': {\'x\': 3, \'z\': 4}})'

    def test_duplicates(self) -> None:
        """Find duplicate values."""
        ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert ns.duplicates() == {'x': [('a',), ('b',)]}

    def test_duplicates_with_filter(self) -> None:
        """Find duplicate values."""
        ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert ns.duplicates(lambda t: t in {'x', }) == {}

    def test_trim(self) -> None:
        """Remove duplicates."""
        ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert ns.trim() == {'a': {'x': 1, 'y': 2}, 'b': {'z': 4}}
        assert ns.trim(lambda t: t in {'x', }) == {'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}}

    def test_trim_fancy(self) -> None:
        """Remove with lambda key."""
        ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        assert ns.trim(key=lambda t: chr(ord('z') - ord(t[0]) + ord('a'))) == {'a': {'y': 2}, 'b': {'x': 3, 'z': 4}}


class TestBuilderConfiguration:
    """Unit tests for BuilderNamespace."""

    def test_repr(self) -> None:
        """Visual representation of BuilderNamespace."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        cfg = BuilderConfiguration(one=one, two=two)
        assert repr(cfg) == (
            'BuilderConfiguration('
            'one=Namespace({\'a\': {\'x\': 1, \'y\': 2}, \'b\': {\'x\': 3, \'z\': 4}}), '
            'two=Namespace({\'b\': {\'x\': 4, \'z\': 2}, \'c\': {\'j\': True, \'k\': 3.14}}))'
        )

    def test_duplicates(self) -> None:
        """Find duplicate values."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        cfg = BuilderConfiguration(one=one, two=two)
        assert cfg.duplicates() == {'x': {'one': [('a',), ('b',)], 'two': [('b',)], '_': []},
                                    'z': {'one': [('b',)], 'two': [('b',)], '_': []}}

    def test_duplicates_with_filter(self) -> None:
        """Find duplicate values."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        cfg = BuilderConfiguration(one=one, two=two)
        assert cfg.duplicates(lambda t: t in {'x', }) == {'z': {'one': [('b',)], 'two': [('b',)], '_': []}}

    def test_trim(self) -> None:
        """Remove duplicates."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        alt = Namespace({'x': 5})
        cfg = BuilderConfiguration(one=one, two=two, alt=alt)
        assert cfg.trim() == (
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {'z': 4}}),
                                 two=Namespace({'b': {}, 'c': {'j': True, 'k': 3.14}}),
                                 alt=Namespace({'x': 5}))
        )

    def test_trim_fancy(self) -> None:
        """Remove with lambda key."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        alt = Namespace({'x': 5})
        cfg = BuilderConfiguration(one=one, two=two, alt=alt)
        assert cfg.trim(lambda t: t in {'x', }).__dict__.items() == (
            BuilderConfiguration(one=Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}}),
                                 two=Namespace({'b': {'x': 4}, 'c': {'j': True, 'k': 3.14}}),
                                 alt=Namespace({'x': 5}))
        ).__dict__.items()

    def test_trim_reverse(self) -> None:
        """Remove duplicates with reverse order of priority."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        alt = Namespace({'x': 5})
        cfg = BuilderConfiguration(one=one, two=two, alt=alt)
        assert cfg.trim(reverse=True) == (
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {}}),
                                 two=Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}}),
                                 alt=Namespace({}))
        )

    def test_trim_ordered(self) -> None:
        """Remove duplicates with preserved order of priority."""
        one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
        two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
        alt = Namespace({'x': 5})
        cfg = BuilderConfiguration(one=one, two=two, alt=alt)
        cfg.update(x=6)
        assert cfg.trim(ordered=True).__dict__.items() == (
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {}}), 
                                 two=Namespace({'b': {'z': 2}, 'c': {'j': True, 'k': 3.14}}),
                                 alt=Namespace({}), 
                                 _=Namespace({'x': 6}))
        ).__dict__.items()
