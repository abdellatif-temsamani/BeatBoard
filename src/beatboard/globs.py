from pathlib import Path
from typing import Literal, Self


def get_cache_db() -> str:
    """Get the path to the cache database.

    Returns:
        The path to the cache database file as a string, always in the
        user-state directory: ~/.local/state/beatboard/cache.db
    """
    return str(Path.home() / ".local" / "state" / "beatboard" / "cache.db")


DebugCategory = Literal[
    "command",
    "palette",
    "cache",
    "perf",
    "api",
    "plugins",
    "all",
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
    hardware: list[str] = ["g213"]
    debug: dict[DebugCategory, bool] = {
        "command": False,
        "palette": False,
        "cache": False,
        "perf": False,
        "api": False,
        "plugins": False,
        "all": False,
    }
    cache_path: str = get_cache_db()
    plugin_dir: str | None = str(Path.home() / ".config" / "beatboard" / "plugins")
    # Spotify pure-websocket globals
    api: bool = False
    spotify: bool = False
    spotify_token: str | None = None
    spotify_refresh_token: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
    spotify_websocket_url: str = "wss://dealer.spotify.com/?access_token={token}"

    def __new__(cls) -> Self:
        """Singleton pattern implementation of the Globs class."""
        if cls.__instance is None:
            cls.__instance = super(Globs, cls).__new__(cls)
        return cls.__instance
