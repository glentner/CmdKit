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

    """Tiny example script using CmdKit."""


    # type annotations
    from __future__ import annotations

    # standard libs
    import os
    import sys

    # external libs
    from cmdkit import Application, Interface

    # metadata
    version = '0.1.0'

    prog_name = os.path.basename(sys.argv[0])
    usage_text = f"""\
    Usage:
      {prog_name} [-v] NAME
      {__doc__}\
    """

    help_text = f"""\
    {usage_text}

    Arguments:
      NAME                  Name of person to greet.

    Options:
      -v, --version         Print version and exit.
      -h, --help            Print this message and exit.\
    """


    class TinyApp(Application):
        """Application class for tiny-script program."""

        interface = Interface(prog_name, usage_text, help_text)
        interface.add_argument('-v', '--version', action='version', version=version)

        name: str
        interface.add_argument('name')

        def run(self: TinyApp) -> None:
            """Run program."""
            print(f'Hello, {self.name}!')


    if __name__ == '__main__':
        sys.exit(TinyApp.main(sys.argv[1:]))


A slightly more sophisticated iteration of this `hello-world` program could include
logging, configuration, and additional parameters to help us understand the state of
the program at runtime.

Try manipulating the configuration files, and environment variables starting with
``FULLHELLO_``, see the ``-s`` and ``-c`` options to see how these changes manifest.


.. code-block:: python

    #!/usr/bin/env python3

    """Full example script using CmdKit."""


    # type annotations
    from __future__ import annotations
    from typing import IO

    # standard libs
    import os
    import sys
    import json
    from getpass import getuser

    # external libs
    from cmdkit.app import Application, exit_status
    from cmdkit.cli import Interface
    from cmdkit.config import Configuration
    from cmdkit.namespace import Namespace
    from cmdkit.logging import Logger, logging_styles, level_by_name

    # metadata
    version = '0.1.0'
    appname = 'FullHello'
    program = os.path.basename(sys.argv[0])


    default_config = Namespace({
        'logging': {
            'style': 'short',
            'level': 'info'
        }
        # Add more configuration here ...
    })


    try:
        ctx, cfg = Configuration.from_context(name=appname, default_config=default_config)
        log = Logger.default(program,
                             level=level_by_name[cfg.logging.level.upper()],
                             format=logging_styles[cfg.logging.style.lower()]['format'])
    except Exception as error:
        print(f'error: {program}: {error}', file=sys.stderr)
        sys.exit(exit_status.bad_config)


    usage_text = f"""\
    Usage:
      {program} [-v] [NAME | --config | --site] [-o FILE]
      {__doc__}\
    """

    help_text = f"""\
    {usage_text}

    Arguments:
      NAME                  Name of person to greet (default: $USER).

    Options:
      -c, --config          Show configuration and exit.
      -s, --site            Show site paths and exit.
      -o, --output    FILE  Path to output file.
      -v, --version         Print version and exit.
      -h, --help            Print this message and exit.\
    """


    site_text = f"""\
    [system]
    data:   {ctx.path.system.lib}
    logs:   {ctx.path.system.log}
    config: {ctx.path.system.config}

    [user]
    data:   {ctx.path.user.lib}
    logs:   {ctx.path.user.log}
    config: {ctx.path.user.config}

    [local]
    data:   {ctx.path.local.lib}
    logs:   {ctx.path.local.log}
    config: {ctx.path.local.config}
    """

    site_text = site_text.replace(
        f'[{ctx.default_site}]',
        f'[{ctx.default_site}] (default)',
    )


    class FullHello(Application):
        """Application class for program."""

        interface = Interface(program, usage_text, help_text)
        interface.add_argument('-v', '--version', action='version', version=version)

        name: str = getuser()
        interface.add_argument('name', nargs='?', default=name)

        show_config: bool = False
        show_site: bool = False
        mode = interface.add_mutually_exclusive_group()
        mode.add_argument('-c', '--config', action='store_true', dest='show_config')
        mode.add_argument('-s', '--site', action='store_true', dest='show_site')

        outpath: str = '-'
        output_stream: IO = sys.stdout
        interface.add_argument('-o', '--output', dest='outpath', default=outpath)

        def run(self: FullHello) -> None:
            """Run program."""
            if self.show_config:
                log.info('Showing configuration')
                print(json.dumps(dict(cfg), indent=4), file=self.output_stream)
            elif self.show_site:
                log.info('Showing site details')
                print(site_text, file=self.output_stream)
            else:
                log.info(f'Greeting user ({self.name})')
                print(f'Hello, {self.name}!', file=self.output_stream)

        def __enter__(self: FullHello) -> Application:
            """Open output file path."""
            if self.outpath != '-':
                self.output_stream = open(self.outpath, mode='w')
            return super().__enter__()

        def __exit__(self: FullHello, *exc) -> None:
            """Close resources."""
            if self.output_stream is not sys.stdout:
                self.output_stream.close()


    if __name__ == '__main__':
        sys.exit(FullHello.main(sys.argv[1:]))


.. note::

    Both of these short programs are included with the project under
    the ``examples/`` directory.

.. toctree::
    :maxdepth: 3
