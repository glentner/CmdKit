# This program is free software: you can redistribute it and/or modify it under the
# terms of the Apache License (v2.0) as published by the Apache Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the Apache License for more details.
#
# You should have received a copy of the Apache License along with this program.
# If not, see <https://www.apache.org/licenses/LICENSE-2.0>.

"""
Configuration management. Classes and interfaces for management application level
parameters. Get a runtime configuration with a namespace-like interface from both
local files and your environment.
"""

# type annotations
from __future__ import annotations
from typing import IO, TypeVar, Callable, Union, Iterable, Any  # noqa (unused Any) FIXME: why?

# standard libs
import os
from collections.abc import Mapping
from functools import reduce
from typing import Any, Dict


DictKeys: type = type({}.keys())
DictValues: type = type({}.values())
DictItems: type = type({}.items())
DictKeyIterator: type = type(iter({}))


class Namespace(dict):
    """
    A dictionary with depth-first updates.

    Example:
    >>> ns = Namespace({'a': {'x': 1, 'y': 2}, 'b': 3})
    >>> ns.update({'a': {'x': 4, 'z': 5}})
    Namespace({'a': {'x': 4, 'y': 2, 'z': 5}, 'b': 3})
    """

    def __init__(self, *args: Union[Iterable, Mapping], **kwargs: Any) -> None:
        """Initialize from same signature as `dict`."""
        super().__init__(*args, **kwargs)

    def __repr__(self) -> str:
        """Convert to string representation."""
        original = super().__repr__()
        return f'{self.__class__.__name__}({original})'

    def __getitem__(self, key: str) -> Any:
        """Like `dict.__getitem__` but return Namespace if value is `dict`."""
        value = super().__getitem__(key)
        if isinstance(value, Mapping):
            return self.__class__(value)
        else:
            return value

    def __setitem__(self, key: str, value: Any) -> None:
        """Strip special type if `value` is Namespace."""
        if isinstance(value, Mapping):
            super().__setitem__(key, dict(value))
        else:
            super().__setitem__(key, value)

    @classmethod
    def __depth_first_update(cls, original: dict, new: dict) -> dict:
        """
        Like normal `dict.update` but if values in both are mappable descend
        a level deeper (recursive) and apply updates there instead.
        """
        for key, value in new.items():
            if isinstance(value, dict) and isinstance(original.get(key), dict):
                original[key] = cls.__depth_first_update(original.get(key, {}), value)
            else:
                original[key] = value
        return original

    def update(self, *args, **kwargs) -> None:
        """Implements a recursive, depth-first update (i.e., an "override")."""
        self.__depth_first_update(self, dict(*args, **kwargs))

    @classmethod
    def from_env(cls, prefix: str = '', defaults: dict = None) -> Namespace:
        """
        Create a `Namespace` from `os.environ`, optionally exclude variables
        based on their name using `prefix`.

        The `defaults` will be used if variables are not found in the
        environment.
        """
        env = cls(defaults or {})
        if not prefix:
            env.update(dict(os.environ))
        else:
            env.update({name: value for name, value in os.environ.items()
                        if name.startswith(prefix)})
        return env

    @classmethod
    def from_local(cls, filepath: str, ignore_if_missing: bool = False, **options) -> Namespace:
        """Generic factory method delegates based on filename extension."""
        ext = os.path.splitext(filepath)[1].lstrip('.')
        if not os.path.exists(filepath) and ignore_if_missing is True:
            return Namespace()
        try:
            factory = getattr(cls, f'from_{ext}')
            return factory(filepath, **options)
        except AttributeError:
            raise NotImplementedError(f'{cls.__class__.__name__} does not currently support "{ext}" files."')

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

    def to_local(self, filepath: str, **options) -> None:
        """Output to local file. Format based on file extension."""
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
                yaml.dump(self, output, **kwargs)
        else:
            yaml.dump(self, path_or_file, **kwargs)

    def to_toml(self, path_or_file: Union[str, IO], encoding: str = 'utf-8', **kwargs) -> None:
        """Output to TOML file."""
        import toml
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='w', encoding=encoding) as output:
                toml.dump(self, output, **kwargs)
        else:
            toml.dump(self, path_or_file, **kwargs)

    def to_json(self, path_or_file: Union[str, IO], encoding: str = 'utf-8', indent: int = 4, **kwargs) -> None:
        """Output to JSON file."""
        import json
        if isinstance(path_or_file, str):
            with open(path_or_file, mode='w', encoding=encoding) as output:
                json.dump(self, output, indent=indent, **kwargs)
        else:
            json.dump(self, path_or_file, indent=indent, **kwargs)

    # short-hand
    from_yml = from_yaml
    from_tml = from_toml
    to_yml = to_yaml
    to_tml = to_toml


# basic types automatically converted from environment variable
ValueType = TypeVar('ValueType', str, int, float, bool, type(None))


class Environ(Namespace):
    """
    A Namespace initialize via Namespace.from_env. The special method
    `.reduce` melts the normalized variables by splitting on underscores.

    Example
    -------
    >>> from cmdkit.config import Environ
    >>> env = Environ('MYAPP')
    >>> env
    Environ({'MYAPP_A_X': 1, 'MYAPP_A_Y': 2, 'MYAPP_B': 3})

    >>> env.reduce()
    Environ({'a': {'x': 1, 'y': 2}, 'b': 3})
    """

    # remembers the prefix for use with `.reduce`
    _prefix: str = ''

    def __init__(self, prefix: str = '', defaults: dict = None) -> None:
        """Built via `Namespace.from_env`."""
        self._prefix = prefix
        ns = Namespace.from_env(prefix=prefix, defaults=defaults)
        super().__init__(ns)

    def reduce(self, converter: Callable[[str], Any] = None) -> Namespace:
        """De-normalize the key-value pairs as a deep dictionary."""
        coerced = converter or self._coerced
        ns = Namespace()
        for key, value in self.items():
            prefix, *sections = key.split('_')
            base = {}
            reduce(lambda d, k: d.setdefault(k.lower(), {}), sections[:-1], base)[sections[-1].lower()] = coerced(value)
            ns.update(base)
        return ns

    @staticmethod
    def _coerced(var: str) -> ValueType:
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


class Configuration:
    """
    An ordered collection of `Namespace` dictionaries.

    Example
    -------
    >>> import os
    >>> from cmdkit.config import Configuration
    >>> HOME, CWD = os.getenv('HOME'), os.getcwd()
    >>> cfg = Configuration.from_local(default={},
    ...                                system='/etc/myapp.yml',
    ...                                user=f'{HOME}/.myapp.yml',
    ...                                local=f'{CWD}/.myapp.yml',
    ...                                env=True, prefix='MYAPP')
    """

    _namespaces: Namespace = None
    _master: Namespace = None

    def __init__(self, **namespaces: Namespace) -> None:
        """Retain source `namespaces` and create master namespace."""
        self._namespaces = Namespace()
        self._master = Namespace()
        self.extend(**namespaces)

    @property
    def namespaces(self) -> Dict[str, Namespace]:
        """Access to namespaces."""
        return self._namespaces

    def __getitem__(self, key: str) -> Any:
        """Access parameter from Configuration."""
        return self._master[key]

    def __repr__(self) -> str:
        """String representation of Configuration."""
        kwargs = ', '.join([f'{k} = ' + v.__repr__()
                            for k, v in self.namespaces.items()])
        return f'Configuration({kwargs})'

    def keys(self) -> DictKeys:
        """A set-like object providing a view on the merged keys"""
        return self._master.keys()

    def values(self) -> DictValues:
        """An object providing a view on the merged values"""
        return self._master.values()

    def extend(self, **others: dict) -> None:
        """Apply update to master dict with `other`."""
        for name, mapping in others.items():
            self._namespaces[name] = Namespace(mapping)
            self._master.update(self.namespaces[name])

    @classmethod
    def from_local(cls, *, env: bool = False, prefix: str = None,
                   default: Mapping = None, **files: str) -> Configuration:
        """Create configuration from cascade of `files`. Optionally include `env`."""
        default_ = Namespace() if not default else Namespace(default)
        cfg = cls(default=default_)
        for label, filepath in files.items():
            cfg.extend(**{label: Namespace.from_local(filepath, ignore_if_missing=True)})
        if env:
            cfg.extend(**{'env': Environ(prefix).reduce()})
        return cfg
