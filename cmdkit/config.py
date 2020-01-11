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
Configuration management. Classes and interfaces for manageming application level
parameters. Get a runtime configuration with a namespace-like interface from both
local files and your environment.
"""

# standard libs
import os
from collections.abc import Mapping
from typing import Any, Dict


DictKeys: type = type({}.keys())
DictValues: type = type({}.values())
DictItems: type = type({}.items())
DictKeyIterator: type = type(iter({}))


class Namespace(dict):
    """
    Base level functionality for specific sub-classes (e.g., Environment).
    A Namespace is a `dict` with additional features and factory methods.
    It also overrides the `update` method to be a depth-first recursive update.

    Example:
    >>> ns = Namespace({'x': 1, 'y': 2})
    >>> ns
    Namespace({'x': 1, 'y': 2})
    """

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

    @staticmethod
    def __depth_first_update(original: dict, new: dict) -> dict:
        """
        Like normal `dict.update` but if values in both are mappable decend
        a level deeper (recursive) and apply updates there instead.
        """
        for key, value in new.items():
            if isinstance(value, Mapping) and isinstance(original.get(key), Mapping):
                original[key] = Namespace.__depth_first_update(original.get(key, {}), value)
            else:
                original[key] = value

        return original

    def update(self, other: dict) -> None:
        """Implements a recursive, depth-first update (i.e., an "override")."""
        self.__depth_first_update(self, other)

    @classmethod
    def from_env(cls, prefix: str = '', defaults: dict = {}) -> None:
        """
        Create a `Namespace` from `os.environ`, optionally exclude variables
        based on their name using `prefix` or `pattern`.
        """
        env = cls(defaults)
        if not prefix:
            env.update(os.environ)
        else:
            env.update({name: value for name, value in os.environ.items()
                        if name.startswith(prefix)})
        return env

    @classmethod
    def from_local(self, filepath: str, **options) -> 'Namespace':
        """Generic factory method delegates based on filename extension."""
        try:
            ext = os.path.splitext(filepath)[1].lstrip('.')
            factory = getattr(self, f'_from_{ext}')
            return factory(filepath, **options)
        except AttributeError:
            raise NotImplementedError(f'{self.__class__.__name__} does not currently support "{ext}" files."')

    @classmethod
    def _from_yaml(cls, filepath: str, **options) -> 'Namespace':
        """Load a namespace from a YAML file."""
        import yaml
        with open(filepath, mode='r', **options) as source:
            return cls(yaml.load(source, Loader=yaml.FullLoader))

    @classmethod
    def _from_toml(cls, filepath: str, **options) -> 'Namespace':
        """Load a namespace from a TOML file."""
        import toml
        with open(filepath, mode='r', **options) as source:
            return cls(toml.load(source))

    @classmethod
    def _from_json(cls, filepath: str, **options) -> 'Namespace':
        """Load a namespace from a JSON file."""
        import json
        with open(filepath, mode='r', **options) as source:
            return cls(json.load(source))

    def to_local(self, filepath: str, **options) -> None:
        """Output to local file. Format based on file extension."""
        try:
            ext = os.path.splitext(filepath)[1].lstrip('.')
            factory = getattr(self, f'_to_{ext}')
            return factory(filepath, **options)
        except AttributeError:
            raise NotImplementedError(f'{self.__class__.__name__} does not currently support "{ext}" files."')

    def _to_yaml(self, filepath: str, encoding: str = 'utf-8', **kwargs) -> None:
        """Output to local YAML file."""
        import yaml
        with open(filepath, mode='w', encoding=encoding) as output:
            yaml.dump(self, output, **kwargs)

    def _to_toml(self, filepath: str, encoding: str = 'utf-8', **kwargs) -> None:
        """Output to local TOML file."""
        import toml
        with open(filepath, mode='w', encoding=encoding) as output:
            toml.dump(self, output, **kwargs)

    def _to_json(self, filepath: str, encoding: str = 'utf-8', indent: int = 4, **kwargs) -> None:
        """Output to local JSON file."""
        import json
        with open(filepath, mode='w', encoding=encoding) as output:
            json.dump(self, output, indent=indent, **kwargs)

    # short-hand
    _from_yml = _from_yaml
    _to_yml = _to_yaml


class Configuration:
    """A collection of `Namespace` dictionaries."""

    _namespaces: Dict[str, Namespace] = {}
    _master: Namespace = Namespace()

    def __init__(self, **namespaces: Namespace) -> None:
        """Retain source `namespaces` and create master namespace."""
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

    def keys(self) -> type({}.keys()):
        """A set-like object providing a view on the merged keys"""
        return self._master.keys()

    def values(self) -> type({}.values()):
        """An object providing a view on the merged values"""
        return self._master.values()

    def extend(self, **others: dict) -> None:
        """Apply update to master dict with `other`."""
        for name, mapping in others.items():
            self._namespaces[name] = Namespace(mapping)
            self._master.update(self.namespaces[name])
