:mod:`cmdkit.ansi`
==================

Utility module provides simple methods to colorize text.
Used by the include :mod:`cmdkit.logging` module to provide
rich highlighting of message attributes.


.. module:: cmdkit.ansi
    :platform: Unix, Windows

|

-------------------

Reference
---------

|

.. py:data:: NO_COLOR
    :type: bool

    ``False`` if environment variable is not present.

.. py:data:: FORCE_COLOR
    :type: bool

    ``False`` if environment variable is not present.

|

.. autoenum:: Ansi


|

.. autofunction:: format_ansi

|

.. autofunction:: bold

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: faint

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: italic

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: underline

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: black

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: red

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: green

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: yellow

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: blue

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: magenta

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: cyan

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

.. autofunction:: white

    Wrapper to :meth:`~cmdkit.ansi.format_ansi` function.

|

.. autofunction:: colorize_usage

|

.. toctree::
    :maxdepth: 3
