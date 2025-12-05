#!/usr/bin/env python3

import asyncio
import subprocess

from src.color_gen import get_color_palette
from src.playerctl import get_image, watch_playerctl


async def handle_art_change(art_url: str):
    """Handle one change event — same logic as your main()."""
    IMAGE_PATH = "/tmp/album_art.jpg"

    # Download or fetch new album art
    await get_image(IMAGE_PATH, art_url)

    # Extract palette
    image_colors = get_color_palette(IMAGE_PATH)

    # Run external script
    subprocess.run(["python", "./G213Colors/G213Colors.py", "-c", image_colors[0]])


async def main():
    await watch_playerctl(handle_art_change)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
