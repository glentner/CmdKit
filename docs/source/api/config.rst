:mod:`cmdkit.config`
====================

.. module:: cmdkit.config
    :platform: Unix, Windows

|

Configuration management. Classes and interfaces for management application level
parameters. Get a runtime configuration with a namespace-like interface from both
local files and your environment.

|

.. note::

    Because of an implementation detail regarding the way nested members are
    handled recursively by these data structures, in-place assignments of such
    nested members will not have an effect.

    These objects are then to be treated as read-only in the sense that they can
    only allow :func:`update` (for :class:`Namespace`) and :func:`extend`
    (for :class:`Configuration`).

|

-------------------

|

.. autoclass:: Namespace
    :show-inheritance:

    |

    .. automethod:: update

    |

    .. automethod:: from_local
    .. automethod:: to_local

    |

    .. automethod:: from_yaml
    .. automethod:: from_toml
    .. automethod:: from_json

    |

    .. automethod:: to_yaml
    .. automethod:: to_toml
    .. automethod:: to_json

    |

    .. automethod:: from_env
    .. automethod:: to_env

|

-------------------

|

.. autoclass:: Environ
    :show-inheritance:

    |

    .. automethod:: expand
    .. automethod:: flatten

    |

    .. automethod:: export

    |

-------------------

|

.. autoclass:: Configuration
    :show-inheritance:

    |

    .. autoattribute:: namespaces

    |

    .. automethod:: extend

    |

    .. automethod:: from_local

    |

    .. automethod:: which

|

.. toctree::
    :maxdepth: 3
    :hidden:
