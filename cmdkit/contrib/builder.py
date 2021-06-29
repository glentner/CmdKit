# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Configuration management Provider. Classes and interfaces for the specific provider
for Namespace and Configuration. The Builder provider extends functionality by allowing
the construction of new-like objects with filtered or otherwise modified contents.

TODO:
    Add capability to return an new-like object with a pop or popitem modification.

"""


# type annotations
from __future__ import annotations
from typing import Tuple, List, Dict, Callable, Optional, Any

# standard libs
import copy
from collections import Counter
from functools import reduce

# internal libs
from ..config import Namespace, Configuration, _find_the_leaves

# public interface
__all__ = ['BuilderNamespace', 'BuilderConfiguration', ]


class BuilderNamespace(Namespace):
    """A Namespace provider, with added methods for creating new-like Namespaces."""
    
    def duplicates(self, function: Optional[Callable[[str], bool]] = None) -> Dict[str, List[Tuple[str, ...]]]:
        """
        Find all the repeated `leaves` which does not meet the filter `function`.

        Example:
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
            >>> ns = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.trim()
            Namespace({'a': {'x': 1, 'y': 2}, 'b': {'z': 4}})

            >>> ns.trim(reverse=True)
            Namespace({'a': {'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.trim(key=lambda t: chr(ord('z') - ord(t[0]) + ord('a')))
            Namespace({'a': {'y': 2}, 'b': {'x': 3, 'z': 4}})
        """
        space = copy.deepcopy(self)
        for name, paths in space.duplicates(function).items():
            unique, *duplicates = sorted(paths, key=key, reverse=reverse)
            for path in duplicates:
                reduce(lambda branch, leaf: branch[leaf], path, space).pop(name)
        return space

class BuilderConfiguration(Configuration):
    """A Configuration provider, with added methods for creating new-like Configurations."""

    def duplicates(self, function: Optional[Callable[[str], bool]] = None) -> Dict[str, Dict[str, List[Tuple[str, ...]]]]:
        """
        Find all the repeated `leaves` which does not meet the filter `function`.

        Example:
            >>> one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
            >>> cfg = Configuration(one=one, two=two)

            >>> cfg.duplicates()
            {'x': {'one': [('a',), ('b',)], 'two': [('b',)]}, 'z': {'one': [('b',)], 'two': [('b',)]}}
        """
        ignore = function if function is not None else lambda _: False
        tips = [tip for _, (*_, tip) in _find_the_leaves(self.namespaces) if not ignore(tip)]
        return {tip: self.whereis(tip) for tip, count in Counter(tips).items() if count > 1}  
    
    def trim(self, function: Optional[Callable[[str], bool]] = None, *,
             key: Callable[[Tuple[str, ...]], Any] = None, reverse: bool = False) -> BuilderConfiguration:
        """
        Return a copy with duplicate `leaves` removed, optionally using a `key` function or `reverse`
        and a filter `function`.

        Example:
            >>> one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
            >>> alt = Namespace({'x': 5})
            >>> cfg = Configuration(one=one, two=two, alt=alt)

            >>> cfg.trim()
            Configuration(one=Namespace({'a': {'y': 2}, 'b': {'z': 4}}), two=Namespace({'b': {}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({'x': 5}))

            >>> cfg.trim(reverse=True)
            Configuration(one=Namespace({'a': {'y': 2}, 'b': {}}), two=Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({}))

            >>> cfg.trim(key=lambda a: a[0][2], reverse=True)
            Configuration(one=Namespace({'a': {'y': 2}, 'b': {}}), two=Namespace({'b': {'z': 2}, 'c': {'j': True, 'k': 3.14}}), alt=Namespace({'x': 5})) 
        """
        lookup = lambda path, source: reduce(lambda branch, leaf: branch[leaf], path, source) 
        config = copy.deepcopy(self)
        for name, spaces in config.duplicates(function).items():
            paths = [(space, *path) for space, paths in spaces.items() for path in paths]
            (unique_space, *unique_path), *duplicates = sorted(paths, key=key, reverse=reverse)
            for space, *path in duplicates:
                if path:
                    lookup(path, config.namespaces[space]).pop(name)
                    lookup(path[1:], config[path[0]]).pop(name, None)
                else:
                    config.namespaces[space].pop(name)
                    config.pop(name, None)
                if unique_path:
                    config[unique_path[0]].update(**config.namespaces[unique_space][unique_path[0]])
        return config
