:mod:`cmdkit.config`
====================

.. module:: cmdkit.config
    :platform: Unix, Windows

|

Configuration management. Classes and interfaces for management application level
parameters. Get a runtime configuration with a namespace-like interface from both
local files and your environment.

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

    .. automethod:: from_env

    |

    .. automethod:: from_yaml
    .. automethod:: from_toml
    .. automethod:: from_json

    |

    .. automethod:: to_yaml
    .. automethod:: to_toml
    .. automethod:: to_json

-------------------

|

.. autoclass:: Environ
    :show-inheritance:

    |

    .. automethod:: reduce

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
