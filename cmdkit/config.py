# SPDX-FileCopyrightText: 2021 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""
Configuration management. Classes and interfaces for managing application level
parameters. Get a runtime configuration with a namespace-like interface from both
local files and your environment.
"""


# type annotations
from __future__ import annotations
from typing import IO, Tuple, List, Dict, NamedTuple, TypeVar, Callable, Union, Iterable, Optional, Any

# standard libs
import os
import functools
import subprocess
from collections.abc import Mapping
from functools import reduce

# public interface
__all__ = ['Namespace', 'Environ', 'Configuration', 'ConfigurationError', ]

# type aliases
DictKeys: type = type({}.keys())
DictValues: type = type({}.values())
DictItems: type = type({}.items())
DictKeyIterator: type = type(iter({}))


T = TypeVar('T')
def _as_namespace(ns: T) -> Union[T, Namespace]:
    """If `ns` is a mappable, coerce to Namespace, recursively, otherwise pass."""
    return ns if not isinstance(ns, Mapping) else Namespace({k: _as_namespace(v) for k, v in dict(ns).items()})


def _as_dict(ns: NSCoreMixin) -> dict:
    """If `ns` is a mappable, coerce to dict, recursively, otherwise pass."""
    return {k: v if not isinstance(v, Mapping) else _as_dict(v) for k, v in dict(ns).items()}


class NSCoreMixin(dict):
    """Core namespace mechanics used by `Namespace` and `Configuration`."""

    def __init__(self, *args: Union[Iterable, Mapping], **kwargs: Any) -> None:
        """Initialize from same signature as `dict`."""
        super().__init__()
        for k, v in dict(*args, **kwargs).items():
            self[k] = _as_namespace(v)

    def __setitem__(self, key: str, value: Any) -> None:
        """Strip special type if `value` is Namespace-like."""
        if not isinstance(value, Mapping):
            super().__setitem__(key, value)
        else:
            super().__setitem__(key, _as_namespace(dict(value)))

    def __setattr__(self, name: str, value: Any) -> None:
        """Alias for index notation (if already present)."""
        if name in self:
            self[name] = value
        else:
            super().__setattr__(name, value)

    @classmethod
    def __depth_first_update(cls, original: dict, new: dict) -> dict:
        """
        Like normal `dict.update` but if values in both are mappable, descend
        a level deeper (recursive) and apply updates there instead.
        """
        for key, value in new.items():
            if isinstance(value, dict) and isinstance(original.get(key), dict):
                original[key] = cls.__depth_first_update(original.get(key, {}), value)
            else:
                original[key] = value
        return original

    def update(self, *args, **kwargs) -> None:
        """Depth-first update method."""
        self.__depth_first_update(self, dict(*args, **kwargs))

    def __getattr__(self, item: str) -> Any:
        """
        Alias for index notation.
        Transparently expand `_env` and `_eval` variants.
        """
        variants = [f'{item}_env', f'{item}_eval']
        if item in self:
            return self[item]
        for variant in variants:
            if variant in self:
                return self.__expand_attr(item)
        else:
            raise AttributeError(f'missing \'{item}\'')

    def __expand_attr(self, item: str) -> str:
        """Interpolate values if `_env` or `_eval` present."""

        getters = {f'{item}': (lambda: self[item]),
                   f'{item}_env': functools.partial(self.__expand_attr_env, item),
                   f'{item}_eval': functools.partial(self.__expand_attr_eval, item)}

        items = [key for key in self if key in getters]
        if len(items) == 0:
            raise ConfigurationError(f'\'{item}\' not found')
        elif len(items) == 1:
            return getters[items[0]]()
        else:
            raise ConfigurationError(f'\'{item}\' has more than one variant')

    def __expand_attr_env(self, item: str) -> str:
        """Expand `item` as an environment variable."""
        return os.getenv(str(self[f'{item}_env']), None)

    def __expand_attr_eval(self, item: str) -> str:
        """Expand `item` as a shell expression."""
        return subprocess.check_output(str(self[f'{item}_eval']), shell=True).decode().strip()

    def __repr__(self) -> str:
        """Convert to string representation."""
        return f'{self.__class__.__name__}({repr(_as_dict(self))})'


class Namespace(NSCoreMixin):
    """
    A dictionary with depth-first updates and factory methods.

    Example:
        >>> ns = Namespace({'a': {'x': 1, 'y': 2}, 'b': 3})
        >>> ns.update({'a': {'x': 4, 'z': 5}})
        >>> ns
        Namespace({'a': {'x': 4, 'y': 2, 'z': 5}, 'b': 3})

        >>> Namespace.from_local('config.toml', ignore_if_missing=True)
        Namespace({})

        >>> Namespace.from_local('config', ftype='toml', ignore_if_missing=True)
        Namespace({})

        >>> ns.to_local('config.toml')
        >>> Namespace.from_local('config.toml', ignore_if_missing=True)
        Namespace({'a': {'x': 4, 'y': 2, 'z': 5}, 'b': 3})
    """

    @classmethod
    def from_dict(cls, other: Dict[str, Any]) -> Namespace:
        """Explicitly create a Namespace from existing dictionary."""
        return cls(other)

    @classmethod
    def from_local(cls, filepath: str, ignore_if_missing: bool = False, ftype: Optional[str] = None,  **options) -> Namespace:
        """if ftype not set,
           Generic factory method delegates based on filename extension.
        """

        if ftype in ('toml', 'tml', 'yaml', 'yml', 'json'):
            ext = ftype
        else:
            ext = os.path.splitext(filepath)[1].lstrip('.')
        if not os.path.exists(filepath) and ignore_if_missing is True:
            return cls()
        try:
            factory = getattr(cls, f'from_{ext}')
            return factory(filepath, **options)
        except AttributeError:
            raise NotImplementedError(f'{cls.__class__.__name__} does not currently support \'{ext}\' files')

    @classmethod
    def from_yaml(cls, path_or_file: Union[str, IO], **options) -> Namespace:
        """Load a namespace from a YAML file."""
        import yaml
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='r', **options) as source:
                return cls(yaml.load(source, Loader=yaml.FullLoader))
        else:
            return cls(yaml.load(path_or_file, Loader=yaml.FullLoader))

    @classmethod
    def from_toml(cls, path_or_file: Union[str, IO], **options) -> Namespace:
        """Load a namespace from a TOML file."""
        import toml
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='r', **options) as source:
                return cls(toml.load(source))
        else:
            return cls(toml.load(path_or_file))

    @classmethod
    def from_json(cls, path_or_file: Union[str, IO], **options) -> Namespace:
        """Load a namespace from a JSON file."""
        import json
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='r', **options) as source:
                return cls(json.load(source))
        else:
            return cls(json.load(path_or_file))

    def to_dict(self) -> Dict[str, Any]:
        """Explicitly coerce a Namespace to dictionary."""
        return _as_dict(self)

    def to_local(self, filepath: str, ftype: Optional[str] = None,  **options) -> None:
        """Output to local file.
           if ftype not set, Format based on file extension."""
        if ftype in ('toml', 'tml', 'yaml', 'yml', 'json'):
            ext = ftype
        else:
            ext = os.path.splitext(filepath)[1].lstrip('.')
        try:
            factory = getattr(self, f'to_{ext}')
            return factory(filepath, **options)
        except AttributeError:
            raise NotImplementedError(f'{self.__class__.__name__} does not currently support "{ext}" files."')

    def to_yaml(self, path_or_file: Union[str, IO], encoding: str = 'utf-8', **kwargs) -> None:
        """Output to YAML file."""
        import yaml
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='w', encoding=encoding) as output:
                yaml.dump(self.to_dict(), output, **kwargs)
        else:
            yaml.dump(self.to_dict(), path_or_file, **kwargs)

    def to_toml(self, path_or_file: Union[str, IO], encoding: str = 'utf-8', **kwargs) -> None:
        """Output to TOML file."""
        import toml
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='w', encoding=encoding) as output:
                toml.dump(self.to_dict(), output, **kwargs)
        else:
            toml.dump(self.to_dict(), path_or_file, **kwargs)

    def to_json(self, path_or_file: Union[str, IO], encoding: str = 'utf-8', indent: int = 4, **kwargs) -> None:
        """Output to JSON file."""
        import json
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='w', encoding=encoding) as output:
                json.dump(self.to_dict(), output, indent=indent, **kwargs)
        else:
            json.dump(self.to_dict(), path_or_file, indent=indent, **kwargs)

    # short-hand
    from_yml = from_yaml
    from_tml = from_toml
    to_yml = to_yaml
    to_tml = to_toml

    @classmethod
    def from_env(cls, prefix: str = None, defaults: Dict[str, Any] = None) -> Environ:
        """
        Create a :class:`~Namespace` from :data:`os.environ`,
        optionally filtering variables based on their name using `prefix`.

        Args:
            prefix (str):
                An optional prefix to filter the environment variables.
                The results will be any variable that starts with this prefix.
            defaults (dict):
                An existing Namespace of defaults to be overriden if
                present in the environment.

        Example:
            >>> Namespace.from_env(prefix='MYAPP', defaults={'MYAPP_LOGGING_LEVEL': 'WARNING', })
            Environ({'MYAPP_LOGGING_LEVEL': 'WARNING', 'MYAPP_COUNT': '42'})

        See Also:
            :class:`~Environ`: adds :func:`~Environ.expand` method
        """
        return Environ(prefix=prefix, defaults=defaults)

    def to_env(self) -> Environ:
        """Translate namespace to an :class:`Environ` namespace."""
        return Environ(defaults=self)

    def whereis(self, leaf: str, value: Union[Callable[[T], bool], T] = lambda _: True) -> List[Tuple[str, ...]]:
        """
        Find paths to `leaf`, optionally filtered on `value`.

        Example:
            >>> ns = Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})
            >>> ns
            Namespace({'a': {'x': 1, 'y': 2}, 'b': {'x': 3, 'z': 4}})

            >>> ns.whereis('x')
            [('a',), ('b',)]

            >>> ns.whereis('x', 1)
            [('a',)]

            >>> ns.whereis('x', lambda v: v % 3 == 0)
            [('b',)]
        """
        check = value if callable(value) else lambda x: x == value
        return [tuple(branch.stem[:-1]) for branch in _find_the_leaves(self)
                if branch.stem[-1] == leaf and check(branch.leaf)]


# basic types automatically converted from environment variable
_VT = TypeVar('_VT', str, int, float, bool, type(None))


def _coerced(var: str) -> _VT:
    """Automatically coerce input `var` to numeric if possible."""
    if var.lower() in ('', 'null'):
        return None
    if var.lower() == 'true':
        return True
    if var.lower() == 'false':
        return False
    try:
        return int(var)
    except (ValueError, TypeError):
        pass
    try:
        return float(var)
    except(ValueError, TypeError):
        return var


def _de_coerced(var: _VT) -> str:
    """Automatically de-coerce input `var` to consistent string value."""
    if var is None:
        return 'null'
    if var is True:
        return 'true'
    if var is False:
        return 'false'
    else:
        return str(var)


# helper function recursively normalizes a dictionary to depth-1.
def _flatten(ns: dict, prefix: str = None) -> dict:
    new = {}
    for key, value in dict(ns).items():
        if not isinstance(value, dict):
            new[key.upper()] = _de_coerced(value)
        else:
            for subkey, subvalue in _flatten(value).items():
                new['_'.join([key.upper(), subkey.upper()])] = _de_coerced(subvalue)
    if prefix is None:
        return new
    else:
        return {f'{prefix}_{key}': value for key, value in new.items()}


class _Leaf(NamedTuple):
    """Definition of a tree leaf."""
    leaf: Any
    stem: list[str]


def _find_the_leaves(tree: Optional[Mapping[str, Any]]) -> List[_Leaf]:
    """Return the leaves (and their stems) of the tree (e.g., Namespace)."""
    leaves = []
    if tree is not None:
        leaves = [_Leaf(_read_a_leaf(stem, tree), stem) for stem in _walk_the_tree(tree)]
    return leaves


def _read_a_leaf(stem: List[str], tree: Mapping[str, Any]) -> Optional[Any]:
    """Read the leaf at the end of the stem on the tree (e.g., Namespace)."""
    try:
        return reduce(lambda branch, leaf: branch[leaf], stem, tree)
    except KeyError:
        return None


def _walk_the_tree(tree: Mapping[str, Any], stem: List[str] = None) -> List[List[str]]:
    """Return the leaves of the branches."""
    stem = stem or []
    leaves = []
    for branch, branches in tree.items():
        leaf = stem + [branch, ]
        if isinstance(branches, dict):
            leaves.extend(_walk_the_tree(branches, leaf))
        else:
            leaves.append(leaf)
    return leaves


class Environ(NSCoreMixin):
    """
    A Namespace initialized via :func:`~Namespace.from_env`.
    The special method :func:`~expand` melts the normalized variables
    by splitting on underscores into a full heirarchy.

    Example:
        >>> env = Namespace.from_env('MYAPP')
        >>> env
        Environ({'MYAPP_A_X': '1', 'MYAPP_A_Y': '2', 'MYAPP_B': '3'})

        >>> env.expand()
        Environ({'a': {'x': 1, 'y': 2}, 'b': 3})
    """

    # remembers the prefix for use with `.reduce`
    _prefix: Optional[str] = None

    def __init__(self, prefix: str = None, defaults: dict = None) -> None:
        """Built via :func:`~Namespace.from_env`."""
        super().__init__(defaults or {})
        self._prefix = prefix
        if prefix is not None:
            self.update({name: value for name, value in os.environ.items()
                         if name.startswith(prefix)})

    def expand(self, converter: Callable[[str], Any] = None) -> Environ:
        """
        De-normalize the key-value pairs into a nested dictionary.
        The `prefix` is stripped away and structure is derived by
        splitting on underscores.

        The `converter` should be a function that accepts an input value
        and returns a new value appropriately coerced. The default converter
        attempts first to coerce a value to an integer if possible, then
        a float, with the exception of the following special values.
        Otherwise, the string remains.

        ======================== ========================
        Input Value              Output Value
        ======================== ========================
        ``''``, ``'null'``       ``None``
        ``'true'`` / ``'false'`` ``True`` / ``False``
        ======================== ========================
        """
        coerced = converter or _coerced
        partial = Namespace({})
        offset = len(self._prefix) + 1
        for key, value in self.items():
            sections = key[offset:].split('_')
            base = {}
            reduce(lambda d, k: d.setdefault(k.lower(), {}),
                   sections[:-1], base)[sections[-1].lower()] = coerced(value)
            partial.update(base)
        ns = Environ()
        ns.update(partial)
        ns._prefix = self._prefix
        return ns

    def reduce(self, *args, **kwargs) -> Environ:
        """Deprecated. See :meth:`expand`."""
        return self.expand(*args, **kwargs)

    def flatten(self, prefix: str = None) -> Environ:
        """
        Collapse a namespace down to a single level by merging keys with their
        parent section by underscore.

        Example:
            >>> env = Namespace.from_env('MYAPP')
            >>> env
            Environ({'MYAPP_A_X': '1', 'MYAPP_A_Y': '2', 'MYAPP_B': '3'})

            >>> env.expand()
            Environ({'a': {'x': 1, 'y': 2}, 'b': 3})

            >>> env.expand().flatten(prefix='MYAPP')
            Environ({'MYAPP_A_X': '1', 'MYAPP_A_Y': '2', 'MYAPP_B': '3'})
        """
        ns = self.__class__(defaults=_flatten(self, prefix=prefix))
        ns._prefix = prefix
        return ns

    def export(self, prefix: str = None) -> None:
        """Calls :meth:`flatten` before persisting members to :data:`os.environ`."""
        env = self.flatten(prefix=prefix)
        for key, value in env.items():
            os.environ[key] = value


class ConfigurationError(Exception):
    """Exception specific to configuration errors."""


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
                super().update(self.namespaces[name])
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

    def which(self, *path: str) -> str:
        """
        Derive which member namespace takes precedent for the given variable.

        Example:
            >>> conf = Configuration(one=Namespace({'x': 1, 'y': 2}),
            ...                      two=Namespace({'x': 3, 'z': 4})
            >>> conf.extend(three=Namespace({'y': 5, 'u': {'i': 6, 'j': 7}}))

            >>> conf.which('x')
            'two'

            >>> conf.which('y')
            'three'

            >>> conf.which('u', 'i')
            'three'
        """
        namespaces = Namespace({**self.namespaces, '_': self.local})
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
        return {name: space.whereis(leaf, value) for name, space in self.namespaces.items()}

    def __setattr__(self, name: str, value: Any) -> None:
        """Intercept parameter assignment."""
        if name in self:
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
            If you ask :func:`which` namespace a parameter has come from and it was an in-place change,
            it will be considered a member of the "_" namespace.

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
        self.local.update(*args, **kwargs)
        super().update(*args, **kwargs)
