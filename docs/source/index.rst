CmdKit
======

Release v\ |release|. (:ref:`Tutorial <tutorial>`)

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

The *cmdkit* library implements a few common patterns needed for commandline tools in Python.
It only touches a few concepts but it implements them well.
The idea is to reduce the boilerplate needed to get a full featured CLI off the ground.
Applications developed using *cmdkit* are easy to implement, easy to maintain, and easy to
understand.

-------------------

Features
--------

- An :class:`~cmdkit.cli.Interface` class for parsing commandline arguments.
- An :class:`~cmdkit.app.Application` class that provides the boilerplate for
  a good entry-point.
- Basic :mod:`~cmdkit.logging` via the `logalpha <https://logalpha.readthedocs.io>`_ package.
- A :class:`~cmdkit.config.Configuration` class built on top of a
  :class:`~cmdkit.config.Namespace` class that provides
  automatic depth-first merging of dictionaries from local files,
  as well as automatic environment variable discovery and type-coercion.

|

-------------------

Installation
------------

*CmdKit* is built on Python 3.7+ and can be installed using Pip.

.. code-block:: none

    ➜ pip install cmdkit

|

-------------------

Getting Started
---------------

Checkout the :ref:`Tutorial <tutorial>` for examples.

You can also checkout how `cmdkit` is being used by other projects.

========================================================  =======================================================
Project                                                   Description
========================================================  =======================================================
`REFITT <https://github.com/refitt/refitt>`_              Recommender Engine for Intelligent Transient Tracking
`hyper-shell <https://github.com/glentner/hyper-shell>`_  Hyper-shell is an elegant, cross-platform, high-performance
                                                          computing utility for processing shell commands over a
                                                          distributed, asynchronous queue.
`delete-cli <https://github.com/glentner/delete-cli>`_    A simple, cross-platform, commandline move-to-trash.
========================================================  =======================================================


-------------------

|

**Table of Contents**

.. toctree::

    api/index
    tutorial/index
    contributing
    license
