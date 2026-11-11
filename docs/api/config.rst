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

Reference
---------

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

    .. automethod:: from_context

    |

    .. automethod:: which

        ``which`` is keyed on the literal key. Where a higher layer's variant of a name has
        displaced a key on the path (``name``, ``name_env`` and ``name_eval`` are one key across
        layers, as above), item access raises ``KeyError`` and so does ``which``, for that key
        and for anything beneath it. In a few rare sequences of in-place changes, ``which`` can
        still answer from a lower layer for a key that item access no longer finds; they are
        tracked on the roadmap.

    |

    .. automethod:: duplicates

    |

    .. automethod:: whereis

    |

    .. automethod:: update

|

.. toctree::
    :maxdepth: 3
    :hidden:
