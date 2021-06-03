:mod:`cmdkit.config`
====================

.. module:: cmdkit.config
    :platform: Unix, Windows

|

Classes and interfaces for managing application level configuration parameters.
Get a runtime configuration with a namespace-like interface from both
local files and environment variables with appropriate precedent.

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

.. note::

    Because of an implementation detail regarding the way the :class:`Configuration`
    class is implemented, using the :func:`update` method directly will have the intended
    effect on the immediate representation of the structure, but knowledge of where that
    change occurred will be lost.

    Similarly, directly modifying parameters will work as expected with the exception that
    the now current value will lose its provenance.

    **This behavior is not considered part of the public API and may in future releases be
    changed without notice and is not considered a major change.**

|

.. toctree::
    :maxdepth: 3
    :hidden:
