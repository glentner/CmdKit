:mod:`cmdkit.platform`
======================

.. module:: cmdkit.platform
    :platform: Unix, Windows

|

Sensible default behavior for applications with platform-specific file paths.

Applications have a `system`, `user`, and `local` path. With respect to configuration files
this ties in with the ideas implemented by :class:`~cmdkit.config.Configuration`. We want to
allow for a cascade of files and environment variables. In addition to the site of configuration,
applications have standard locations for any data they may need or create as well as a place
for log files, telemetry, or tracebacks.

The :class:`~cmdkit.platform.AppContext` data class holds these conventional paths and other
context. The :meth:`~cmdkit.platform.AppContext.default` constructor builds these paths following
platform-specific conventions.

Platform-Specific Paths
-----------------------

Assuming the following basic initialization, we initialize these file paths.

.. code-block:: python

    context = AppContext.default('MyApp', create_dirs=True, config_format='toml')


Windows
^^^^^^^

**System**

- ``context.path.system.lib``: ``%PROGRAMDATA%\MyApp\Library``
- ``context.path.system.log``: ``%PROGRAMDATA%\MyApp\Logs``
- ``context.path.system.config``: ``%PROGRAMDATA%\MyApp\Config.toml``

**User**

- ``context.path.user.lib``: ``%APPDATA%\MyApp\Library``
- ``context.path.user.log``: ``%APPDATA%\MyApp\Logs``
- ``context.path.user.config``: ``%APPDATA%\MyApp\Config.toml``

**Local**

- ``context.path.local.lib``: ``%MYAPP_SITE%\Library``
- ``context.path.local.log``: ``%MYAPP_SITE%\Logs``
- ``context.path.local.config``: ``%MYAPP_SITE%\Config.toml``

macOS
^^^^^

**System**

- ``context.path.system.lib``: ``/Library/MyApp``
- ``context.path.system.log``: ``/Library/MyApp/Logs``
- ``context.path.system.config``: ``/Library/Preferences/MyApp/config.toml``

**User**

- ``context.path.user.lib``: ``$HOME/Library/MyApp``
- ``context.path.user.log``: ``$HOME/Library/MyApp/Logs``
- ``context.path.user.config``: ``$HOME/Library/Preferences/MyApp/config.toml``

**Local**

- ``context.path.local.lib``: ``$MYAPP_SITE/Library``
- ``context.path.local.log``: ``$MYAPP_SITE/Logs``
- ``context.path.local.config``: ``$MYAPP_SITE/config.toml``

Linux / POSIX
^^^^^^^^^^^^^

**System**

- ``context.path.system.lib``: ``/var/lib/myapp``
- ``context.path.system.log``: ``/var/log/myapp``
- ``context.path.system.config``: ``/etc/myapp.toml``

**User**

- ``context.path.user.lib``: ``$HOME/.myapp/lib``
- ``context.path.user.log``: ``$HOME/.myapp/log``
- ``context.path.user.config``: ``$HOME/.myapp/config.toml``

**Local**

- ``context.path.local.lib``: ``$MYAPP_SITE\lib``
- ``context.path.local.log``: ``$MYAPP_SITE\log``
- ``context.path.local.config``: ``$MYAPP_SITE\config.toml``

If the environment variable ``MYAPP_SITE`` is not defined, the `local` site defaults to
the ``.myapp`` in the current working directory.


|

-------------------

Reference
---------

|

.. autoclass:: AppContext

    .. automethod:: default

        If ``create_dirs=True``, we create the ``default_site`` directies if needed.
        The ``default_site`` corresponds to the ``default_path`` extracted from ``path``,
        and is ``local`` if the application `site` environment variable exists,
        otherwise ``user``.

        Available configuration formats are ``toml``, ``yaml``, and ``json``.

    .. autoattribute:: cwd

        The current working directory.

    .. autoattribute:: home

        The user's home directory (platform specific).

    .. autoattribute:: name

        The application name (``MyApp`` in the above example).

    .. autoattribute:: path

        A hierarchical :class:`~cmdkit.config.Namespace` mapping out file paths.
        Each of the members ``system``, ``user``, and ``local`` have keys
        ``lib`` (directory), ``log`` (directory) , and ``config`` (file).

    .. autoattribute:: default_site

        Either ``local`` or ``user`` depending on whether the application
        `site` environment variable was defined.

    .. autoattribute:: default_path

        Section of `path` extracted by name depending on ``default_site``.

|

.. toctree::
    :maxdepth: 3
