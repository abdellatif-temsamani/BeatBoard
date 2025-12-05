import colorsys
from typing import Tuple

from colorthief import ColorThief
from PIL import Image


def debug_pallete(palette: list[Tuple[int, int, int]]) -> None:
    """Show the palette in a matplotlib window"""

    import matplotlib.pyplot as plt

    plt.imshow([[palette[i] for i in range(len(palette))]])
    plt.show()


def get_color_palette(path: str) -> list[str]:
    """Get the color palette from the image"""

    theif: ColorThief = ColorThief(path)

    palette: list[Tuple[int, int, int]] = theif.get_palette(color_count=10)

    filtered_colors: list[Tuple[int, int, int]] = []

    for r, g, b in palette:
        # Convert RGB to HLS
        _, lightness, saturation = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)

        # Skip neutral colors
        if saturation < 0.3 or lightness < 0.2 or lightness > 0.85:
            continue

        filtered_colors.append((r, g, b))

    # fallback if all colors are filtered
    if not filtered_colors:
        filtered_colors = palette

    # Load image to count pixels
    img = Image.open(path).convert("RGB")
    pixels = [p for p in img.getdata()]

    def color_count(rgb):
        return sum(1 for p in pixels if p == rgb)

    # Sort by how common each color is (descending)
    filtered_colors.sort(key=color_count, reverse=True)

    # Convert to hex
    hex_colors = [f"{r:02x}{g:02x}{b:02x}" for r, g, b in filtered_colors]

    return hex_colors
