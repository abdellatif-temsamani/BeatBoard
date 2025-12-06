from typing import Self

from .keyboard_support import KeyboardName


class Globs:
    """
    A singleton class used to store shared global data across the application.

    This class guarantees that only one instance ever exists.
    Any access to ``Globs()`` will return the same shared instance,
    allowing different parts of the program to read or update
    common values consistently.

    Attributes:
        _instance: Holds the singleton instance. Automatically managed internally.
        keyboard: The name of the keyboard currently in use. Defaults to an empty string.
    """

    __instance: Self | None = None
    keyboard: KeyboardName = "g213"

    def __new__(cls):
        if cls.__instance is None:
            cls.__instance = super(Globs, cls).__new__(cls)
            cls.__instance.keyboard = "g213"
        return cls.__instance
