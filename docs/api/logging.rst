:mod:`cmdkit.logging`
=====================

.. module:: cmdkit.logging
    :platform: Unix, Windows


An extension of the standard library's :mod:`logging` module.

We extend the :class:`~cmdkit.logging.Logger` and the
:class:`~cmdkit.logging.LogRecord` implementations to allow for
an extended range of levels and attributes. Also included is a
preset definition of logging `styles`.

Merely importing this module in your application will trigger the
extensions; which will have an effect on any package using the
standard logging implementation.

|

-------------------

Reference
---------

|

.. autoclass:: Logger

    .. automethod:: with_name

    .. automethod:: default


|

.. autoclass:: LogRecord

    New program-level attributes.

    .. autoattribute:: app_id

        A UUID specific to the running Python process.

    .. autoattribute:: hostname

        Output of ``socket.gethostname()``.

    .. autoattribute:: hostname_short

        Trimmed version of ``hostname`` without subdomains.

    .. autoattribute:: relative_name

        Trimmed version of the program ``name`` without
        the leading package; e.g., ``mypackage.server`` becomes ``server``.

    |

    Available :class:`~cmdkit.ansi.Ansi` escape sequences.
    The value of ``ansi_level`` corresponds to the defined
    :data:`~cmdkit.logging.level_color` mapping for the current record's level.

    .. autoattribute:: ansi_level
    .. autoattribute:: ansi_reset
    .. autoattribute:: ansi_bold
    .. autoattribute:: ansi_faint
    .. autoattribute:: ansi_italic
    .. autoattribute:: ansi_underline
    .. autoattribute:: ansi_black
    .. autoattribute:: ansi_red
    .. autoattribute:: ansi_green
    .. autoattribute:: ansi_yellow
    .. autoattribute:: ansi_blue
    .. autoattribute:: ansi_magenta
    .. autoattribute:: ansi_cyan
    .. autoattribute:: ansi_white

    |

    Newly available time attributes. Beyond the standard ``%(asctime)s`` you
    can use one of the following formats with respect to the elapsed time since
    application start.

    .. autoattribute:: elapsed

        The current elapsed time in seconds.

    .. autoattribute:: elapsed_ms

        The current elapsed time in milliseconds.

    .. autoattribute:: elapsed_delta

        The current elapsed time as formatted by ``datetime.timedelta``.

    .. autoattribute:: elapsed_hms

        The current elapsed time formatted as ``dd-hh:mm:ss.sss``.

|

.. py:data:: HOSTNAME
    :type: str

    Result of call to :meth:`socket.gethostname`.

.. py:data:: HOSTNAME_SHORT
    :type: str

    Trimmed version of :data:`HOSTNAME` with only the
    initial part of the domain.

.. py:data:: INSTANCE
    :type: str

    A UUID (:meth:`uuid.uuid4`) unique to the Python process.

|

.. py:data:: level_by_name
    :type: Dict[str, int]

    Get the actual `level` from its ``str`` representation.

    .. code-block:: python

        levelname = 'info'
        level = level_by_name[levelname.upper()]

.. py:data:: logging_styles
    :type: Dict[str, Dict[str, str]]

    Dictionary containing preset definitions (essentially just the `format`).
    Other things would be named parameters to :meth:`Logger.default`
    (or the standard library :meth:`logging.basicConfig`).

    Available styles include:

    - ``default`` (colorized level, module name)
    - ``short`` (colorized level name only)
    - ``detailed`` (colorized time stamp, hostname, level name, module name)
    - ``detailed-compact`` (colorized relative time stamp, short hostname, level name, relative module name)
    - ``system`` (similar to ``detailed`` but without colorization and includes application UUID).

    .. code-block:: python

        import os
        from cmdkit.logging import Logger, level_by_name, logging_styles

        level = os.getenv('MYAPP_LOGGING_LEVEL', 'INFO')
        style = os.getenv('MYAPP_LOGGING_STYLE', 'DEFAULT')

        log = Logger.default(name='myapp',
                             level=level_by_name[level.upper()],
                             **logging_styles[style.lower()])

.. py:data:: DEFAULT_LOGGING_STYLE
    :type: str
    :value: 'default'

    Used by :meth:`Logger.default` to select from :data:`logging_styles` dictionary.

|

.. py:data:: NOTSET
    :type: int
    :value: 0

.. py:data:: DEVEL
    :type: int
    :value: 1

.. py:data:: TRACE
    :type: int
    :value: 5

.. py:data:: DEBUG
    :type: int
    :value: 10

.. py:data:: INFO
    :type: int
    :value: 20

.. py:data:: NOTICE
    :type: int
    :value: 25

.. py:data:: WARNING
    :type: int
    :value: 30

.. py:data:: ERROR
    :type: int
    :value: 40

.. py:data:: CRITICAL
    :type: int
    :value: 50

|

.. toctree::
    :maxdepth: 3
