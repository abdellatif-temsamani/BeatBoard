#!/usr/bin/env python3

import asyncio

from rich import print


async def beatboard_main():
    """
    Main entry point for BeatBoard.

    Parses command-line arguments, sets up global state,
    and starts the playerctl watching process.
    """
    # Import here to avoid relative import issues at module level
    from .args import parser
    from .globs import Globs
    from .playerctl import watch_playerctl

    args = parser.parse_args()

    globs = Globs()
    globs.hardware = args.hardware
    globs.debug = args.debug

    await watch_playerctl(args.follow)


def main():
    """Synchronous wrapper for the async main function."""
    try:
        asyncio.run(beatboard_main())
    except KeyboardInterrupt:
        print("\nShutting down...")


if __name__ == "__main__":
    main()
