#!/usr/bin/env python3

import asyncio

from rich import print

from src.args import parser
from src.globs import Globs
from src.playerctl import watch_playerctl


async def main():
    """Main function"""

    args = parser.parse_args()

    globs = Globs()
    globs.hardware = args.hardware
    globs.debug = args.debug

    await watch_playerctl(args.follow)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
