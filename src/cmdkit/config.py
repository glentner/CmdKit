# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Configuration management. Classes and interfaces for managing application level
parameters. Get a runtime configuration with a namespace-like interface from both
local files and your environment.
"""


# type annotations
from __future__ import annotations
from typing import Tuple, List, Dict, TypeVar, Callable, Union, Any, Mapping

# standard libs
from collections import Counter

# internal libs
from cmdkit.namespace import NSCoreMixin, Namespace, Environ, _find_the_leaves
from cmdkit.platform import AppContext

# public interface
__all__ = [
    'Configuration', 'ConfigurationError',
    'Namespace', 'Environ',  # Re-exported for backwards compatibility
]

# type aliases
T = TypeVar('T')


class ConfigurationError(Exception):
    """Exception specific to configuration errors."""


_MISSING = object()


def _variant_siblings(key: Any) -> List[str]:
    """The other keys that are a variant of a name `key` is a variant of."""
    if not isinstance(key, str):
        return []
    names = [key]
    if key.endswith('_env'):
        names.append(key[:-4])
    if key.endswith('_eval'):
        names.append(key[:-5])
    return [other for name in names for other in (name, f'{name}_env', f'{name}_eval') if other != key]


def _drop_displaced_variants(target: dict, new: Mapping) -> None:
    """
    Remove from `target` every variant of a name that `new` sets a different variant of,
    at every level where the depth-first update will descend.
    """
    for key, value in new.items():
        for other in _variant_siblings(key):
            if other in target and other not in new:
                del target[other]
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _drop_displaced_variants(target[key], value)


def _apply_layer(target: NSCoreMixin, new: Mapping) -> None:
    """Depth-first update of `target` with `new`, where the variants `new` sets displace the others."""
    _drop_displaced_variants(target, new)
    NSCoreMixin.update(target, new)


def _value_at(mapping: Any, path: Tuple[Any, ...]) -> Any:
    """The value at `path` through nested mappings, or `_MISSING`."""
    for key in path:
        if not isinstance(mapping, dict) or key not in mapping:
            return _MISSING
        mapping = mapping[key]
    return mapping


def _lacks(mapping: Any, path: Tuple[Any, ...]) -> bool:
    """Whether item access along `path` raises `KeyError`: a mapping on the way lacks the next key."""
    for key in path:
        if not isinstance(mapping, dict):
            return False
        if key not in mapping:
            return True
        mapping = mapping[key]
    return False


def _displaced(sources: List[Mapping], path: Tuple[Any, ...]) -> bool:
    """
    Whether, above a source that holds all of `path`, a source sets another variant
    of a key on `path` in that key's place, and not the key itself.
    """
    held = False
    for source in sources:
        for depth, key in enumerate(path):
            parent = _value_at(source, path[:depth])
            if held and isinstance(parent, dict) and key not in parent \
                    and any(other in parent for other in _variant_siblings(key)):
                return True
        held = held or _value_at(source, path) is not _MISSING
    return False


class Configuration(NSCoreMixin):
    """
    An ordered collection of `Namespace` dictionaries.
    The update behavior of :class:`~Namespace` is used to
    provide a layering effect for configuration parameters.

    Example:
        >>> conf = Configuration(one=Namespace({'x': 1, 'y': 2}),
        ...                      two=Namespace({'x': 3, 'z': 4})

        >>> conf
        Configuration(one=Namespace({'x': 1, 'y': 2}), two=Namespace({'x': 3, 'z': 4}))

        >>> conf.x, conf.y, conf.z
        (3, 2, 4)

        >>> conf.namespaces.keys()
        dict_keys(['one', 'two'])

        >>> conf.namespaces.one.x
        1

    A parameter `name` and its `name_env` and `name_eval` variants are one key across
    the layers: the highest layer that sets any of them decides, and only the variants
    it sets remain in the merged view. Within a single layer, two variants of one name
    are still ambiguous.

    Example:
        >>> conf = Configuration(one=Namespace({'db': {'password': 'secret'}}),
        ...                      two=Namespace({'db': {'password_eval': 'echo other'}}))

        >>> dict(conf)
        {'db': Namespace({'password_eval': 'echo other'})}

        >>> conf.db.password
        'other'

        >>> conf.which('db', 'password_eval')
        'two'
    """

    local: Namespace  # NOTE: used to track changes to the 'self'
    namespaces: Namespace

    def __init__(self, **namespaces: Namespace) -> None:
        """Retain source `namespaces` and create master namespace."""
        super().__init__()
        self.local = Namespace()
        self.namespaces = Namespace()
        self.extend(**namespaces)

    def __repr__(self) -> str:
        """String representation of Configuration."""
        kwargs = ', '.join([f'{k}=' + repr(v) for k, v in self.namespaces.items()])
        if self.local:
            kwargs += f', _={repr(self.local)}'
        return f'{self.__class__.__name__}({kwargs})'

    def extend(self, **others: Union[Namespace, Environ]) -> None:
        """
        Extend the configuration by adding namespaces.

        Example:
            >>> conf = Configuration(one=Namespace({'x': 1, 'y': 2}),
            ...                      two=Namespace({'x': 3, 'z': 4})
            >>> conf.extend(three=Namespace({'y': 5, 'u': {'i': 6, 'j': 7}}))
            >>> conf
            Configuration(one=Namespace({'x': 1, 'y': 2}),
                          two=Namespace({'x': 3, 'z': 4}),
                          three=Namespace({'y': 5, 'u': {'i': 6, 'j': 7}})
        """
        for name, mapping in others.items():
            if name != '_':
                self.namespaces[name] = Namespace(mapping)
                _apply_layer(self, self.namespaces[name])
            else:
                self.local.update(mapping)

    @classmethod
    def from_local(cls, *, env: bool = False, prefix: str = None,
                   default: dict = None, **files: str) -> Configuration:
        """
        Create configuration from a cascade of `files`. Optionally include `env`.

        Example:
            >>> import os
            >>> HOME, CWD = os.getenv('HOME'), os.getcwd()
            >>> conf = Configuration.from_local(default=Namespace(),
            ...                                 env=True, prefix='MYAPP',
            ...                                 system='/etc/myapp.yml',
            ...                                 user=f'{HOME}/.myapp.yml',
            ...                                 local=f'{CWD}/.myapp.yml')
        """
        default_ = Namespace() if not default else Namespace(default)
        cfg = cls(default=default_)
        for label, filepath in files.items():
            cfg.extend(**{label: Namespace.from_local(filepath, ignore_if_missing=True)})
        if env:
            cfg.extend(env=Environ(prefix).reduce())
        return cfg

    @classmethod
    def from_context(cls,
                     name: str,
                     create_dirs: bool = True,
                     config_format: str = 'toml',
                     default_config: dict = None) -> Tuple[AppContext, Configuration]:
        """
        Build default configuration from application context.

        This builder method is shorthand for calling :meth:`~cmdkit.platform.AppContext.default`
        on :class:`~cmdkit.platform.AppContext` and passing it into :meth:`Configuration.from_local`
        with environment variables enabled and `system`, `user`, and `local` passed accordingly.

        Example:
            >>> default_cfg = Namespace(logging={'level': 'info'}, server={'port': 54321})
            >>> ctx, cfg = Configuration.from_context('myapp', default_config=default_cfg)

        On Linux, you would get ``/etc/myapp.toml`` as a `system` configuration,
        ``~/.myapp.toml`` as a `user` configuration and ``$MYAPP_SITE/config.toml`` as the
        `local` site.
        """
        context = AppContext.default(name, create_dirs=create_dirs, config_format=config_format)
        return (
            context,
            cls.from_local(env=True, prefix=context.name.upper(),
                           system=context.path.system.config,
                           user=context.path.user.config,
                           local=context.path.local.config,
                           default=default_config)
        )

    def which(self, *path: str) -> str:
        """
        Derive which member namespace takes precedent for the given variable.

        Example:
            >>> conf = Configuration(one=Namespace({'x': 1, 'y': 2}),
            ...                      two=Namespace({'x': 3, 'z': 4}))
            >>> conf.extend(three=Namespace({'y': 5, 'u': {'i': 6, 'j': 7}}))

            >>> conf.which('x')
            'two'

            >>> conf.which('y')
            'three'

            >>> conf.which('u', 'i')
            'three'

        Note:
            Care needs to be taken when used for mutable variables in the
            stack as the returned precedent does not reflect that the variable
            at that level may be a depth-first-merge of several sources.

            >>> conf = Configuration(one=Namespace({'a': {'x': 1, 'y': 2}}),
            ...                      two=Namespace({'a': {'y': 3}}))

            >>> conf.which('a')
            'two'

            >>> conf.a
            Namespace({'x': 1, 'y': 3})
        """
        namespaces = Namespace({**self.namespaces, '_': self.local})
        if _lacks(self, path) and _displaced(list(namespaces.values()), path):
            raise KeyError(f'Not found: {path}')
        for label in reversed(list(namespaces.keys())):
            try:
                sub = namespaces[label]
                for p in path:
                    sub = sub[p]
                return label
            except KeyError:
                pass
        else:
            raise KeyError(f'Not found: {path}')

    def duplicates(self) -> Dict[str, Dict[str, List[Tuple[str, ...]]]]:
        """
        Find all the repeated `leaves`.

        Example:
            >>> one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> two = Namespace({'b': {'x': 4, 'z': 2}, 'c': {'j': True, 'k': 3.14}})
            >>> cfg = Configuration(one=one, two=two)

            >>> cfg.duplicates()
            {'x': {'one': [('a',), ('b',)], 'two': [('b',)]}, 'z': {'one': [('b',)], 'two': [('b',)]}}
        """
        namespaces = Namespace({**self.namespaces, '_': self.local})
        tips = [tip for _, (*_, tip) in _find_the_leaves(namespaces)]
        return {tip: self.whereis(tip) for tip, count in Counter(tips).items() if count > 1}

    def whereis(self, leaf: str,
                value: Union[Callable[[T], bool], T] = lambda _: True) -> Dict[str, List[Tuple[str, ...]]]:
        """
        Find paths to `leaf`, optionally filtered on `value`, for each member namespace.

        Example:
            >>> one = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> two = Namespace({'b': {'x': 4}, 'c': {'j': True, 'k': 3.14}})
            >>> cfg = Configuration(one=one, two=two)

            >>> cfg.whereis('x')
            {'one': [('a',), ('b',)], 'two': [('b',)]}

            >>> cfg.whereis('x', 1)
            {'one': [('a',)], 'two': []}

            >>> cfg.whereis('x', lambda v: v % 3 == 0)
            {'one': [('b',)], 'two': []}
        """
        namespaces = Namespace({**self.namespaces, '_': self.local})
        return {name: space.whereis(leaf, value) for name, space in namespaces.items()}

    def __setattr__(self, name: str, value: Any) -> None:
        """Intercept parameter assignment."""
        if name in self or any(other in self for other in _variant_siblings(name)):
            self.update({name: value})
        else:
            super().__setattr__(name, value)

    def update(self, *args, **kwargs) -> None:
        """
        Update current namespace directly.

        Note:
            The :class:`Configuration` class is itself a :class:`Namespace`-like object.
            Doing any in-place changes to its underlying `self` does not change its member namespaces.
            This may otherwise cause confusion about the provenance of those parameters.
            Instead, overrides have been implemented to capture these changes in a `local` namespace.
            If you ask :func:`which` namespace a parameter has come from, and it was an in-place change,
            it will be considered a member of the "_" namespace.
            An in-place change follows the same rule as the layers for `_env` and `_eval`
            variants: setting one variant of a name replaces any other variant of that name,
            both in the "_" namespace and in the merged view.

        Example:
            >>> conf = Configuration(a=Namespace(x=1))
            >>> conf
            Configuration(a=Namespace({'x': 1}))

            >>> conf.update(y=2)
            >>> conf
            Configuration(a=Namespace({'x': 1}), _=Namespace({'y': 2}))

            >>> conf.x = 2
            >>> conf
            Configuration(a=Namespace({'x': 1}), _=Namespace({'x': 2, 'y': 2}))

            >>> conf.update(y=3)
            >>> conf
            Configuration(a=Namespace({'x': 1}), _=Namespace({'x': 2, 'y': 3}))

            >>> dict(conf)
            {'x': 2, 'y': 3}
        """
        _apply_layer(self.local, dict(*args, **kwargs))
        _apply_layer(self, dict(*args, **kwargs))

    def pop(self, *args, **kwargs) -> Any:
        """
        It is not straight forward to implement the equivalent of super().update() for
        the general case; currently disallow pop() on `Configuration`.
        """
        raise NotImplementedError(f'{self.__class__.__name__} does not currently support pop()')

    def popitem(self) -> Tuple[str, Any]:
        """
        It is not straight forward to implement the equivalent of super().update() for
        the general case; currently disallow popitem() on `Configuration`.
        """
        raise NotImplementedError(f'{self.__class__.__name__} does not currently support popitem()')
