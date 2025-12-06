from typing import Self

from .hardware import hardwareName


class Globs:
    """
    A singleton class used to store shared global data across the application.

    This class guarantees that only one instance ever exists.
    Any access to ``Globs()`` will return the same shared instance,
    allowing different parts of the program to read or update
    common values consistently.

    Attributes:
        _instance: Holds the singleton instance. Automatically managed internally.
        hardware: the list of hardware devices to be used
        debug: whether to print debug messages
    """

    __instance: Self | None = None
    hardware: list[hardwareName] = ["g213"]
    debug: bool = False

    def __new__(cls) -> Self:
        """Singleton pattern implementation of the Globs class."""
        if cls.__instance is None:
            cls.__instance = super(Globs, cls).__new__(cls)
        return cls.__instance
