:mod:`cmdkit.logging`
=====================

.. module:: cmdkit.logging
    :platform: Unix, Windows

Logging in :mod:`cmdkit` is done using :mod:`logalpha`. There are only a few
places where logging occurs, most notably in the :class:`~cmdkit.app.Application`
class for argument errors.

The :data:`log` instance created here is suitable for general purpose logging
out-of-the-box for many basic situations. Messages are printed to <stderr> with
one of `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` levels. The default
level is `WARNING`.

.. note::

    You can change the default level by altering the level of the member
    :class:`ConsoleHandler`.

    Example:
        >>> from cmdkit.logging import log, LEVELS
        >>> log.info('hello')
        >>> log.handlers[0].level = LEVELS[1]
        >>> log.info('hello')
        INFO hello

.. warning::

    If you create your own logger (either using :mod:`logging` from the standard library
    or even with :mod:`logalpha`) you will need to inject that logger back into the
    :mod:`cmdkit` library. You will also need to set the :func:`~cmdkit.app.Application.log_error`
    method of the :class:`~cmdkit.app.Application` class appropriately.

|

.. autoclass:: ConsoleHandler
    :show-inheritance:

|

.. autodata:: log

.. toctree::
    :maxdepth: 3
    :hidden:
