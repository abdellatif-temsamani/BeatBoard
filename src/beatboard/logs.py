from rich import print

from .globs import DebugCategory, Globs


def log(category: DebugCategory, message: str) -> None:
    """General logging function for different categories."""
    if Globs().debug.get(category):
        print(message)
