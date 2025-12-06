#!/usr/bin/env python3

import asyncio
import subprocess

from src.color_gen import get_color_palette
from src.playerctl import get_image, watch_playerctl


async def process_art_url(art_url: str):
    """process art work of the current song

    Args:
        art_url: The new album art URL.
    """
    IMAGE_PATH = "/tmp/album_art.jpg"

    # Download or fetch new album art
    await get_image(IMAGE_PATH, art_url)

    # Extract palette
    image_colors = get_color_palette(IMAGE_PATH)

    # Run external script
    subprocess.run(["python", "./G213Colors/G213Colors.py", "-c", image_colors[0]])


async def main():
    """Main function"""
    await watch_playerctl(process_art_url)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
