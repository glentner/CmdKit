# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Configuration management Provider. Classes and interfaces for the specific provider
for Namespace and Configuration. The Builder provider extends functionality by allowing
the construction of new-like objects with filtered or otherwise modified contents.

TODO:
    - Add capability to return an new-like object with a pop or popitem modification.
    - Refactor `_find_the_leaves` to be part of the class.
"""


# type annotations
from __future__ import annotations
from typing import Tuple, List, Dict, Callable, Optional, Any

# standard libs
import copy
from collections import Counter
from functools import reduce

# internal libs
from cmdkit.config import Configuration
from cmdkit.namespace import Namespace, _find_the_leaves

# public interface
__all__ = ['BuilderNamespace', 'BuilderConfiguration', ]


class BuilderNamespace(Namespace):
    """A Namespace provider, with added methods for creating new-like Namespaces."""

    def duplicates(self, function: Optional[Callable[[str], bool]] = None) -> Dict[str, List[Tuple[str, ...]]]:
        """
        Find all the repeated `leaves` which does not meet the filter `function`.

        Example:
            >>> ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> ns
            BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.duplicates()
            {'x': [('a',), ('b',)]}

            >>> ns.duplicates(lambda t: t in {'x', })
            {}
        """
        ignore = function if function is not None else lambda _: False
        tips = [tip for _, (*_, tip) in _find_the_leaves(self) if not ignore(tip)]
        return {tip: self.whereis(tip) for tip, count in Counter(tips).items() if count > 1}

    def trim(self, function: Optional[Callable[[str], bool]] = None, *,
             key: Optional[Callable[[Tuple[str, ...]], Any]] = None, reverse: bool = False) -> Namespace:
        """
        Return a copy with duplicate `leaves` removed, optionally using a `key` function or `reverse`
        and a filter `function`.

        Example:
            >>> ns = BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.trim()
            BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'z': 4}})

            >>> ns.trim(lambda t: t in {'x', })
            BuilderNamespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.trim(reverse=True)
            BuilderNamespace({'a': {'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.trim(key=lambda t: chr(ord('z') - ord(t[0]) + ord('a')))
            BuilderNamespace({'a': {'y': 2}, 'b': {'x': 3, 'z': 4}})
        """
        space = copy.deepcopy(self)
        for name, paths in space.duplicates(function).items():
            _, *duplicates = sorted(paths, key=key, reverse=reverse)
            for path in duplicates:
                reduce(lambda branch, leaf: branch[leaf], path, space).pop(name)
        return space


class BuilderConfiguration(Configuration):
    """A Configuration provider, with added methods for creating new-like Configurations."""

    def duplicates(self,
                   function: Optional[Callable[[str], bool]] = None) -> Dict[str, Dict[str, List[Tuple[str, ...]]]]:
        """
        Find all the repeated `leaves` which does not meet the filter `function`.

        Example:
            >>> one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
            >>> cfg = BuilderConfiguration(one=one, two=two)

            >>> cfg.duplicates()
            {'x': {'one': [('a',), ('b',)], 'two': [('b',)]}, 'z': {'one': [('b',)], 'two': [('b',)]}}
        """
        ignore = function if function is not None else lambda _: False
        namespaces = Namespace({**self.namespaces, '_': self.local})
        tips = [tip for _, (*_, tip) in _find_the_leaves(namespaces) if not ignore(tip)]
        return {tip: self.whereis(tip) for tip, count in Counter(tips).items() if count > 1}

    def trim(self, function: Optional[Callable[[str], bool]] = None, *,
             key: Callable[[Tuple[str, ...]], Any] = None, reverse: bool = False,
             ordered: bool = False) -> BuilderConfiguration:
        """
        Return a copy with duplicate `leaves` removed, optionally using a `key` function or `reverse`
        and a filter `function`, or preseving the `ordered` entry into the configuration.

        Example:
            >>> one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
            >>> alt = Namespace({'x': 5})
            >>> cfg = BuilderConfiguration(one=one, two=two, alt=alt)

            >>> cfg.trim()
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {'z': 4}}),
                                 two=Namespace({'b': {}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({'x': 5}))

            >>> cfg.trim(lambda t: t in {'x', })
            BuilderConfiguration(one=Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}}),
                                 two=Namespace({'b': {'x': 4}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({'x': 5}))

            >>> cfg.trim(reverse=True)
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {}}),
                                 two=Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({}))

            >>> cfg.trim(key=lambda a: a[0][2], reverse=True)
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {}}),
                                 two=Namespace({'b': {'z': 2}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({'x': 5}))

            >>> cfg.update(x=6)
            >>> cfg.trim(ordered=True)
            BuilderConfiguration(one=Namespace({'a': {'y': 2}, 'b': {}}),
                                 two=Namespace({'b': {'z': 2}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({}),
                                 _=Namespace({'x': 6}))

            >>> cfg.trim(ordered=True, reverse=True)
            BuilderConfiguration(one=Namespace({'a': {'x': 1, 'y': 2}, 'b': {'z': 4}}),
                                 two=Namespace({'b': {}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({}))
        """
        lookup = lambda path, source: reduce(lambda branch, leaf: branch[leaf], path, source)
        if ordered:
            order = list(Namespace({**self.namespaces, '_': self.local}).keys())
            if reversed: order.reverse()
            key = lambda a: order.index(a[0])
        config = copy.deepcopy(self)
        for name, spaces in config.duplicates(function).items():
            paths = [(space, *path) for space, paths in spaces.items() for path in paths]
            (unique_space, *unique_path), *duplicates = sorted(paths, key=key, reverse=reverse)
            for space, *path in duplicates:
                if path:
                    lookup(path, config.namespaces[space]).pop(name)
                    lookup(path[1:], config[path[0]]).pop(name, None)
                else:
                    if space == '_':
                        config.local.pop(name)
                    else:
                        config.namespaces[space].pop(name)
                    if unique_path and name in config:
                        del config[name]
            if unique_path:
                config[unique_path[0]].update(**config.namespaces[unique_space][unique_path[0]])
        return config
