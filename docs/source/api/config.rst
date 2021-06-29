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

    .. automethod:: duplicates

    |

    .. automethod:: whereis

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

    .. automethod:: duplicates

    |

    .. automethod:: whereis

    |

    .. automethod:: update

|

.. toctree::
    :maxdepth: 3
    :hidden:
