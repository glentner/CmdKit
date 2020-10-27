CmdKit
======

A library for developing command-line applications in Python.

.. image:: https://img.shields.io/badge/license-Apache-blue.svg?style=flat
    :target: https://www.apache.org/licenses/LICENSE-2.0
    :alt: License

.. image:: https://img.shields.io/pypi/v/cmdkit.svg?style=flat&color=blue
    :target: https://pypi.org/project/cmdkit
    :alt: PyPI Version

.. image:: https://img.shields.io/pypi/pyversions/cmdkit.svg?logo=python&logoColor=white&style=flat
    :target: https://pypi.org/project/cmdkit
    :alt: Python Versions

.. image:: https://readthedocs.org/projects/cmdkit/badge/?version=latest&style=flat
    :target: https://cmdkit.readthedocs.io
    :alt: Documentation

.. image:: https://pepy.tech/badge/cmdkit
    :target: https://pepy.tech/badge/cmdkit
    :alt: Downloads

|

The *cmdkit* library implements a few common patterns needed by well-formed command-line
applications in Python. It only touches a few concepts but it implements them well.
The idea is to reduce the boilerplate needed to get a full featured CLI off the ground.
Applications developed using *cmdkit* are easy to implement, easy to maintain, and easy to
understand.

|

Features
--------

- An `Interface <https://cmdkit.readthedocs.io/en/latest/api/cli.html#cmdkit.cli.Interface>`_
  class for parsing command-line arguments.
- An `Application <https://cmdkit.readthedocs.io/en/latest/api/app.html#cmdkit.app.Application>`_
  class that provides the boilerplate for a good entry-point.
- A `Configuration <https://cmdkit.readthedocs.io/en/latest/api/config.html#cmdkit.config.Configuration>`_
  class built on top of a recursive
  `Namespace <https://cmdkit.readthedocs.io/en/latest/api/config.html#cmdkit.config.Namespace>`_
  class that provides automatic depth-first merging of dictionaries from local files,
  as well as automatic environment variable discovery and type-coercion.

|

Installation
------------

*CmdKit* is built on Python 3.7+ and can be installed using Pip.

.. code-block::

    ➜ pip install cmdkit

|

Getting Started
---------------

See the `Tutorial <https://cmdkit.readthedocs.io/en/latest/tutorial/>`_ for examples.

You can also checkout how `cmdkit` is being used by other projects.

========================================================  =======================================================
Project                                                   Description
========================================================  =======================================================
`REFITT <https://github.com/refitt/refitt>`_              Recommender Engine for Intelligent Transient Tracking
`hyper-shell <https://github.com/glentner/hyper-shell>`_  Hyper-shell is an elegant, cross-platform, high-performance
                                                          computing utility for processing shell commands over a
                                                          distributed, asynchronous queue.
`delete-cli <https://github.com/glentner/delete-cli>`_    A simple, cross-platform, command-line move-to-trash.
========================================================  =======================================================

|


Documentation
-------------

Documentation for getting started, the API, and common recipes are available at
`cmdkit.readthedocs.io <https://cmdkit.readthedocs.io>`_.

|

Contributions
-------------

Contributions are welcome in the form of suggestions for additional features, pull requests with
new features or bug fixes, etc. If you find bugs or have questions, open an *Issue* here. If and
when the project grows, a code of conduct will be provided along side a more comprehensive set of
guidelines for contributing; until then, just be nice.
