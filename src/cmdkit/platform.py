# SPDX-FileCopyrightText: 2022 CmdKit Developers
# SPDX-License-Identifier: Apache-2.0

"""Platform specific file paths and initialization."""


# type annotations
from __future__ import annotations
from typing import Tuple, Type

# standard libs
import os
import re
import ctypes
import platform
from dataclasses import dataclass

# internal libs
from cmdkit.config import Namespace, ConfigurationError

# public interface
__all__ = ['cwd', 'home', 'AppContext']


cwd = os.getcwd()
home = os.path.expanduser('~')


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
    is_admin: bool
    default_site: str
    default_path: Namespace
    path: Namespace

    @classmethod
    def default(cls: Type[AppContext],
                appname: str,
                create_dirs: bool = False,
                config_format: str = 'toml') -> AppContext:
        """Define default context with platform-specific paths."""

        if not re.match(r'[a-zA-Z0-9_-]+$', appname):
            raise ValueError(f'Invalid application name, \'{appname}\'')

        site_var = f'{appname.upper()}_SITE'
        local_site = os.getenv(site_var, os.path.join(cwd, f'.{appname.lower()}'))

        if platform.system() == 'Windows':
            is_admin, path = _get_windows_paths(appname, config_format, local_site)
        elif platform.system() == 'Darwin':
            is_admin, path = _get_darwin_paths(appname, config_format, local_site)
        elif os.name == 'posix':
            is_admin, path = _get_posix_paths(appname, config_format, local_site)
        else:
            raise RuntimeError(f'Unrecognized platform: {platform.system()} ({os.name})')

        if site_var in os.environ:
            default_site = 'local'
            default_path = path['local']
        else:
            default_site = 'site' if not is_admin else 'system'
            default_path = path['user'] if not is_admin else path['system']

        if create_dirs:
            os.makedirs(default_path['lib'], exist_ok=True)
            os.makedirs(default_path['log'], exist_ok=True)

        return cls(cwd=cwd, home=home, is_admin=is_admin,
                   default_site=default_site, default_path=default_path, path=path)


def _get_posix_paths(appname: str, config_format: str, local_site: str) -> Tuple[bool, Namespace]:
    """Define paths for generic Posix systems (e.g., Linux)."""
    appname_lower = appname.lower()
    is_admin = os.getuid() == 0
    site = dict(system='/', user=os.path.join(home, f'.{appname_lower}'), local=local_site)
    path = dict({
        'system': {
            'lib': os.path.join(site['system'], 'var', 'lib', appname_lower),
            'log': os.path.join(site['system'], 'var', 'log', appname_lower),
            'config': os.path.join(site['system'], 'etc', f'{appname_lower}.{config_format}')},
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


def _get_darwin_paths(appname: str, config_format: str, local_site: str) -> Tuple[bool, Namespace]:
    """Define paths for Darwin systems (i.e., macOS)."""
    is_admin = os.getuid() == 0
    site = dict(system='/', user=home, local=local_site)
    path = dict({
        'system': {
            'lib': os.path.join(site['system'], 'Library', appname),
            'log': os.path.join(site['system'], 'Library', 'Logs', appname),
            'config': os.path.join(site['system'], 'Library', 'Preferences', appname, f'config.{config_format}')},
        'user': {
            'lib': os.path.join(site['user'], 'Library', appname),
            'log': os.path.join(site['user'], 'Library', 'Logs', appname),
            'config': os.path.join(site['user'], 'Library', 'Preferences', appname, f'config.{config_format}')},
        'local': {
            'lib': os.path.join(site['local'], 'Library'),
            'log': os.path.join(site['local'], 'Logs'),
            'config': os.path.join(site['local'], f'Config.{config_format}')}
    })
    return is_admin, Namespace(path)


def _get_windows_paths(appname: str, config_format: str, local_site: str) -> Tuple[bool, Namespace]:
    """Define paths for Windows systems (NT)."""
    is_admin = ctypes.windll.shell32.IsUserAnAdmin() == 1
    site = dict(system=os.path.join(os.getenv('ProgramData'), appname),
                user=os.path.join(os.getenv('AppData'), appname),
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
