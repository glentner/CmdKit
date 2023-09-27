:mod:`cmdkit.cli`
==================

.. module:: cmdkit.cli
    :platform: Unix, Windows

-------------------

Reference
---------

|

.. autoclass:: Interface
    :show-inheritance:

|


.. seealso::

    The :mod:`argparse` module from the standard library, specifically the
    :class:`~argparse.ArgumentParser` class for the API. The :class:`Interface` class
    simply modifies the behavior of :class:`~argparse.ArgumentParser` to not exit but
    instead raise exceptions, as well as disable the auto-documentation aspect for
    `usage` and `help` statements.

|

.. note::
    The following exceptions allow the :class:`~cmdkit.app.Application` class to catch
    events and handle them instead of the default behavior in :class:`~argparse.ArgumentParser`
    to print and call :func:`~sys.exit`.

|

.. autoclass:: HelpOption
    :show-inheritance:

|

.. autoclass:: VersionOption
    :show-inheritance:

|

.. autoclass:: ArgumentError
    :show-inheritance:


.. toctree::
    :maxdepth: 3