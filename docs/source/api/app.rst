:mod:`cmdkit.app`
=================

The :class:`~Application` class provides structure to commandline interfaces.
Create a new derived application class to share the common boilerplate among
all the entry-points in your project.


.. module:: cmdkit.app
    :platform: Unix, Windows

|

-------------------

|

.. autoclass:: Application

    |

    .. autoattribute:: interface

        The commandline argument parser for this application.
        Calls to :func:`~cmdkit.cli.Interface.add_argument` should have their destination
        set to class-level attribute names.

        .. code-block:: python

            class MyApp(Application):
                ...

                interface = Interface('myapp', 'usage text', 'help text')

                output: str = '-'
                interface.add_argument('-o', '--output', default=output)

                debug_mode: bool = False
                interface.add_argument('-d', '--debug', action='store_true', dest='debug_mode')

    |

    .. autoattribute:: ALLOW_NOARGS

        By default, if the ``cmdline`` list of arguments passed to :func:`~Application.main`
        is empty, the usage text is printed to ``sys.stdout`` and ``exit_status.success``
        is returned.

        If instead the application should proceed to its ``run`` method even in the
        absence of any arguments, set ``ALLOW_NOARGS`` as a class-level attribute.

        .. code-block::

            class MyApp(Application):
                ...

                ALLOW_NOARGS = True

    |

    .. autoattribute:: exceptions

        Map of exceptions to catch and their associated handler.
        The handlers should take an :class:`~Exception` instance as the single argument
        and return an integer value as the exit status to use.

        .. code-block:: python

            def log_and_exit(status: int, error: Exception) -> int:
                """Log the error message as critical and exit with `status`."""
                log.critical(' - '.join(error.args))
                return status

            class MyApp(Application):
                ...

                exceptions = {
                    ConfigurationError:
                        functools.partial(log_and_exit, exit_status.bad_config),
                }

    |

    .. autoattribute:: Application.log_error
        :annotation: : Callable[[str], None] = <bound method Logger.critical of <logalpha.loggers.Logger>>

        A bound method used by :func:`~main` to log error messages.
        In the main try/except block, this method is called with a message.
        This can be overridden by any function with the same interface.
        It is recommended to override this with your own logger.

    |

    .. automethod:: from_cmdline

    |

    .. automethod:: from_namespace

    |

    .. automethod:: main

        The main method should be exposed as an *entry-point* in your ``setup.py`` script.

        .. code-block:: python

            def main() -> int:
                return MyApp.main(sys.argv[1:])

        .. code-block:: python

            setup(
                ...
                # if main() is in myapp.__init__
                entry_points = {'console_script': ['myapp=myapp:main']}
            )

    |

    .. automethod:: run

        .. code-block:: python

            class MyApp(Application):
                ...

                def run(self) -> None:
                    log.info('started')

    |

    .. automethod:: __enter__

        The :func:`~main` method will essentially call the following on your behalf.

        .. code-block:: python

            with MyApp.from_cmdline(...) as app:
                app.run()

        Placing resource acquisition code here makes it easy to ensure that the proper
        tear down procedures happen. If you need to open files or acquire connections,
        place the closing methods in :func:`~__exit__`.

        .. code-block:: python

            class MyApp(Application):
                ...

                output: str = '-'
                output_file: IO = sys.stdout
                interface.add_argument('-o', '--output', default=output)

                def __enter__(self) -> MyApp:
                    """Open output file if necessary."""
                    if self.output != '-':
                        self.output_file = open(self.output, mode='w')

                def __exit__(self, *exc) -> None:
                    """Close output file if necessary."""
                    if self.output != '-':
                        self.output_file.close()

    |

    .. automethod:: __exit__

|

-------------------

|

.. autodata:: exit_status

    This namespace of integer values provides structure to exit status management.
    It is used internally by the :class:`~Application` class. These values can be
    changed by re-assigning them.

|

.. toctree::
    :maxdepth: 3
