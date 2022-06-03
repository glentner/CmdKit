.. _simple_script:

A Simple Script
===============

To create your first simple program using `cmdkit`, define a basic
:class:`~cmdkit.app.Application` class for structuring your entry-point.
This associates the command-line :class:`~cmdkit.cli.Interface` with the
business logic or your program, defined by the :meth:`~cmdkit.app.Application.run`
method.

Essentially, we want to map the necessary parameters to some function that might
define our task. The expected design defines class-level attributes as our
command-line arguments and parameters. The interface parses these from the raw
arguments. Our :meth:`~cmdkit.app.Application.main` method accepts the raw
arguments and passes the parsed namespace to the constructor of the class,
assigning them to these class-level attributes.


.. code-block:: python

    #!/usr/bin/env python3

    """A simple adding program."""


    # standard libs
    import sys
    import logging

    # external libs
    from cmdkit.app import Application
    from cmdkit.cli import Interface


    USAGE_TEXT = """\
    usage: add [-h] [-v] <NUM> <NUM>
    Add two numbers together.\
    """

    HELP_TEXT = f"""\
    {USAGE_TEXT}

    arguments:
    NUM              Numerical value (e.g., 3.14).

    options:
    -v, --version    Show version and exit.
    -h, --help       Show this message and exit.\
    """


    # basic application logger
    logging.basicConfig(format='add: %(message)s')


    class Add(Application):
        """Application class for adding program."""

        interface = Interface('add', USAGE_TEXT, HELP_TEXT)
        interface.add_argument('-v', '--version', action='version', version='0.0.1')

        lhs: float
        rhs: float
        interface.add_argument('lhs', type=float)
        interface.add_argument('rhs', type=float)

        def run(self) -> None:
            """Business logic of the application."""
            print(self.lhs + self.rhs)


    if __name__ == '__main__':
        sys.exit(Add.main(sys.argv[1:]))


.. toctree::
    :maxdepth: 3
