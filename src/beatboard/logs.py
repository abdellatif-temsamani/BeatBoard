from rich import print

from .globs import DebugCategory, Globs


def log(category: DebugCategory, message: str) -> None:
    """General logging function for different categories."""
    dbg = Globs().debug
    if dbg.get(category) or dbg.get("all"):
        print(message)
