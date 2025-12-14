import platform
from pathlib import Path
from typing import Literal, Self

from .hardware import hardwareName


def get_cache_db() -> str:
    """Get the path to the cache database based on the operating system.

    Returns:
        The path to the cache database directory as a string.
    """
    app_name: str | None = "beatboard"
    system = platform.system()

    if system == "Linux":
        base = Path.home() / ".cache"
    elif system == "Darwin":  # macOS
        base = Path.home() / "Library" / "Caches"
    elif system == "Windows":
        base = Path.home() / "AppData" / "Local"
    else:
        base = Path.cwd() / "cache"

    final = base / app_name if app_name else base
    return str(final)


DebugCategory = Literal[
    "command",
    "palette",
    "cache",
]


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
        cache_path: path to sqlite cache db
    """

    __instance: Self | None = None
    hardware: list[hardwareName] = ["g213"]
    debug: dict[DebugCategory, bool] = {
        "command": False,
        "palette": False,
        "cache": False,
    }
    cache_path: str = get_cache_db()

    def __new__(cls) -> Self:
        """Singleton pattern implementation of the Globs class."""
        if cls.__instance is None:
            cls.__instance = super(Globs, cls).__new__(cls)
        return cls.__instance
