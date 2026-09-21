import asyncio

from rich import print

from .cache.db import source_migrations
from .args import parser
from .globs import Globs
from .hardware import detect_hardware
from .playerctl import check_spotify_available, watch_playerctl


async def beatboard_main():
    """
    Main entry point for BeatBoard.

    Parses command-line arguments, sets up global state,
    and starts the playerctl watching process.
    """
    args = parser.parse_args()

    selected_hardware = args.hardware
    if selected_hardware is None:
        selected_hardware = detect_hardware()
        if not selected_hardware:
            print(
                "[red bold]Error:[/red bold] No supported hardware detected. "
                "Connect a supported device or select one with --hardware."
            )
            return
        print(
            "[green bold]Detected hardware:[/green bold] "
            + ", ".join(selected_hardware)
        )

    if not check_spotify_available():
        print(
            "[red bold]Error:[/red bold] Spotify app not found. Please ensure Spotify is installed and running."
        )
        return

    globs = Globs()
    globs.hardware = selected_hardware

    # Set debug categories based on --debug arguments
    for category in args.debug:
        globs.debug[category] = True

    source_migrations()

    await watch_playerctl(args.once)


def main():
    """Synchronous wrapper for the async main function."""
    try:
        asyncio.run(beatboard_main())
    except KeyboardInterrupt:
        print("\nShutting down...")
