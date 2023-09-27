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
