#!/usr/bin/env python3

import colorsys
import subprocess
from typing import Tuple

from PIL import Image

IMAGE_PATH = "/tmp/album_art.jpg"


def debug_pallete(palette: list[Tuple[int, int, int]]) -> None:

    import matplotlib.pyplot as plt

    plt.imshow([[palette[i] for i in range(len(palette))]])
    plt.show()


def get_image() -> None:

    import requests

    url = subprocess.run(
        ["playerctl", "--player=spotify", "metadata", "mpris:artUrl"],
        capture_output=True,
        text=True,
    )

    url = url.stdout.strip()

    if url.startswith("file://"):
        path = url[7:]  # remove 'file://'
        with open(path, "rb") as f:
            image_data = f.read()
    else:
        # Download via HTTP(S)
        response = requests.get(url)
        response.raise_for_status()  # ensure we got the file
        image_data = response.content

    # Save to a local file
    with open(IMAGE_PATH, "wb") as f:
        f.write(image_data)


def get_color_palette() -> list[str]:
    from colorthief import ColorThief

    ct = ColorThief(IMAGE_PATH)

    palette = ct.get_palette(color_count=10)

    filtered_colors = []

    for r, g, b in palette:
        # Convert RGB to HLS
        _, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

        # Skip neutral colors
        if s < 0.3 or l < 0.2 or l > 0.85:
            continue

        filtered_colors.append((r, g, b))

    # fallback if all colors are filtered
    if not filtered_colors:
        filtered_colors = palette

    # Load image to count pixels
    img = Image.open(IMAGE_PATH).convert("RGB")
    pixels = [p for p in img.getdata()]

    def color_count(rgb):
        return sum(1 for p in pixels if p == rgb)

    # Sort by how common each color is (descending)
    filtered_colors.sort(key=color_count, reverse=True)

    # Convert to hex
    hex_colors = [f"{r:02x}{g:02x}{b:02x}" for r, g, b in filtered_colors]

    return hex_colors


if __name__ == "__main__":

    image = get_image()
    colors = get_color_palette()

    subprocess.run(["python", "./G213Colors/G213Colors.py", "-c", colors[0]])
