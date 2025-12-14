import asyncio

from rich import print

from .cache.db import source_migrations
from .args import parser
from .globs import Globs
from .playerctl import check_spotify_available, watch_playerctl


async def beatboard_main():
    """
    Main entry point for BeatBoard.

    Parses command-line arguments, sets up global state,
    and starts the playerctl watching process.
    """
    args = parser.parse_args()

    if not check_spotify_available():
        print(
            "[red bold]Error:[/red bold] Spotify app not found. Please ensure Spotify is installed and running."
        )
        return

    globs = Globs()
    globs.hardware = args.hardware

    # Set debug categories based on --debug arguments
    for category in args.debug:
        globs.debug[category] = True

    source_migrations()

    await watch_playerctl(args.follow)


def main():
    """Synchronous wrapper for the async main function."""
    try:
        asyncio.run(beatboard_main())
    except KeyboardInterrupt:
        print("\nShutting down...")
