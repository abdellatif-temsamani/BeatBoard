#!/usr/bin/env python3

import asyncio
import subprocess

from rich import print

from src.args import parser
from src.color_gen import get_color_palette
from src.globs import Globs
from src.hardware import get_command
from src.playerctl import get_image, watch_playerctl


async def process_art_url(art_url: str | None = None):
    """process art work of the current song

    Args:
        art_url: The new album art URL.
    """
    IMAGE_PATH = "/tmp/album_art.jpg"

    # Download or fetch new album art
    await get_image(IMAGE_PATH, art_url)

    # Extract palette
    image_colors = get_color_palette(IMAGE_PATH)

    commands = [*get_command(Globs().hardware, image_colors[0])]

    for command in commands:
        print(f"Running command: {command}")
        subprocess.run(command)


async def main():
    """Main function"""

    args = parser.parse_args()

    Globs().hardware = args.hardware
    await watch_playerctl(process_art_url, follow=args.follow)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
