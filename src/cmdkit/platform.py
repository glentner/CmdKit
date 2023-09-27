# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Platform specific file paths and initialization."""


# type annotations
from __future__ import annotations
from typing import Tuple, Type, Final

# standard libs
import os
import re
import ctypes
import platform
from dataclasses import dataclass

# internal libs
from cmdkit.namespace import Namespace

# public interface
__all__ = ['CWD', 'HOME', 'AppContext']


CWD: Final[str] = os.getcwd()
HOME: Final[str] = os.path.expanduser('~')


@dataclass
class AppContext:
    """
    Runtime application context.

    Defines filesystem paths for system, user, and local site.
    Depends on platform and whether runtime environment is admin or user space.
    The 'default' path mapping references the one identified by 'default_site'.
    """

    cwd: str
    home: str
    name: str
    is_admin: bool
    default_site: str
    default_path: Namespace
    path: Namespace

    @classmethod
    def default(cls: Type[AppContext],
                name: str,
                create_dirs: bool = True,
                config_format: str = 'toml') -> AppContext:
        """Define default context with platform-specific paths."""

        if not re.match(r'[a-zA-Z0-9_-]+$', name):
            raise ValueError(f'Invalid application name, \'{name}\'')

        site_var = f'{name.upper()}_SITE'
        local_site = os.getenv(site_var, os.path.join(CWD, f'.{name.lower()}'))

        if platform.system() == 'Windows':
            is_admin, path = _get_windows_paths(name, config_format, local_site)
        elif platform.system() == 'Darwin':
            is_admin, path = _get_darwin_paths(name, config_format, local_site)
        elif os.name == 'posix':
            is_admin, path = _get_posix_paths(name, config_format, local_site)
        else:
            raise RuntimeError(f'Unrecognized platform: {platform.system()} ({os.name})')

        if site_var in os.environ:
            default_site = 'local'
            default_path = path['local']
        else:
            default_site = 'user' if not is_admin else 'system'
            default_path = path['user'] if not is_admin else path['system']

        if create_dirs:
            os.makedirs(default_path['lib'], exist_ok=True)
            os.makedirs(default_path['log'], exist_ok=True)

        return cls(cwd=CWD, home=HOME, name=name, is_admin=is_admin,
                   default_site=default_site, default_path=default_path, path=path)


def _get_posix_paths(name: str, config_format: str, local_site: str) -> Tuple[bool, Namespace]:
    """Define paths for generic Posix systems (e.g., Linux)."""
    name_lower = name.lower()
    is_admin = os.getuid() == 0
    site = dict(system='/', user=os.path.join(HOME, f'.{name_lower}'), local=local_site)
    path = dict({
        'system': {
            'lib': os.path.join(site['system'], 'var', 'lib', name_lower),
            'log': os.path.join(site['system'], 'var', 'log', name_lower),
            'config': os.path.join(site['system'], 'etc', f'{name_lower}.{config_format}')},
        'user': {
            'lib': os.path.join(site['user'], 'lib'),
            'log': os.path.join(site['user'], 'log'),
            'config': os.path.join(site['user'], f'config.{config_format}')},
        'local': {
            'lib': os.path.join(site['local'], 'lib'),
            'log': os.path.join(site['local'], 'log'),
            f'config': os.path.join(site['local'], f'config.{config_format}')}
    })
    return is_admin, Namespace(path)


def _get_darwin_paths(name: str, config_format: str, local_site: str) -> Tuple[bool, Namespace]:
    """Define paths for Darwin systems (i.e., macOS)."""
    is_admin = os.getuid() == 0
    site = dict(system='/', user=HOME, local=local_site)
    path = dict({
        'system': {
            'lib': os.path.join(site['system'], 'Library', name),
            'log': os.path.join(site['system'], 'Library', 'Logs', name),
            'config': os.path.join(site['system'], 'Library', 'Preferences', name, f'config.{config_format}')},
        'user': {
            'lib': os.path.join(site['user'], 'Library', name),
            'log': os.path.join(site['user'], 'Library', 'Logs', name),
            'config': os.path.join(site['user'], 'Library', 'Preferences', name, f'config.{config_format}')},
        'local': {
            'lib': os.path.join(site['local'], 'Library'),
            'log': os.path.join(site['local'], 'Logs'),
            'config': os.path.join(site['local'], f'config.{config_format}')}
    })
    return is_admin, Namespace(path)


def _get_windows_paths(name: str, config_format: str, local_site: str) -> Tuple[bool, Namespace]:
    """Define paths for Windows systems (NT)."""
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
    site = dict(system=os.path.join(os.getenv('ProgramData'), name),
                user=os.path.join(os.getenv('AppData'), name),
                local=local_site)
    path = dict({
        'system': {
            'lib': os.path.join(site['system'], 'Library'),
            'log': os.path.join(site['system'], 'Logs'),
            'config': os.path.join(site['system'], f'Config.{config_format}')},
        'user': {
            'lib': os.path.join(site['user'], 'Library'),
            'log': os.path.join(site['user'], 'Logs'),
            'config': os.path.join(site['user'], f'Config.{config_format}')},
        'local': {
            'lib': os.path.join(site['local'], 'Library'),
            'log': os.path.join(site['local'], 'Logs'),
            'config': os.path.join(site['local'], f'Config.{config_format}')}
    })
    return is_admin, Namespace(path)
