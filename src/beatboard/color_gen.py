import colorsys
from typing import List, Optional, Tuple

from colorthief import ColorThief
from matplotlib.colors import to_rgb
from PIL import Image

from .globs import Globs
from .utils import run_in_main_thread


def debug_palette(
    hex_colors: Optional[List[str]] = None,
    palette: Optional[List[Tuple[int, int, int]]] = None,
) -> None:
    """Show one or both color palettes in one matplotlib window, with labels.

    Args:
        hex_colors: A list of hex color codes without the # symbol.
        palette: A list of RGB color tuples (0-255).

    Raises:
        ValueError: If neither `hex_colors` nor `palette` is provided, or if all provided palettes are empty.
    """
    import matplotlib.pyplot as plt

    if hex_colors is None and palette is None:
        raise ValueError("You must pass either `hex_colors` or `palette`.")

    rows: list[list[tuple[float, float, float]]] = []
    labels: list[str] = []

    # Hex palette
    if hex_colors is not None:
        hex_rgb = [to_rgb("#" + c) for c in hex_colors]
        if hex_rgb:  # Only add if not empty
            rows.append(hex_rgb)
            labels.append("final colors")

    # RGB palette
    if palette is not None:
        palette_rgb = [(r / 255, g / 255, b / 255) for r, g, b in palette]
        if palette_rgb:  # Only add if not empty
            rows.append(palette_rgb)
            labels.append("extracted palette")

    # Filter out any empty rows (shouldn't happen with the above checks, but being safe)
    filtered_rows = []
    filtered_labels = []
    for row, label in zip(rows, labels):
        if len(row) > 0:
            filtered_rows.append(row)
            filtered_labels.append(label)

    if not filtered_rows:
        raise ValueError("At least one non-empty palette must be provided")

    rows = filtered_rows
    labels = filtered_labels

    # Normalize lengths (trim to shortest)
    min_len = min(len(row) for row in rows)
    rows = [row[:min_len] for row in rows]

    # Plot
    _, ax = plt.subplots(figsize=(min_len * 0.5, len(rows) * 1))

    ax.imshow(rows)

    # Add labels
    for i, label in enumerate(labels):
        ax.text(
            -0.5,  # Slightly left of the first column
            i,  # Row index
            label,
            va="center",
            ha="right",
            fontsize=12,
            fontweight="bold",
            color="white",
            backgroundcolor="black",  # Clean contrast
        )

    plt.show()


async def get_color_palette(path: str) -> list[str]:
    """Get the color palette from the image

    Args:
        path: The path to the image to get the palette from.

    Returns:
        list[str]: A list of hex color codes without the # symbol.
    """
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

    def color_count(rgb) -> int:
        """
        Count how many pixels match a specific RGB value.

        Args:
            rgb (tuple[int, int, int]):
                The RGB color to match against each pixel.

        Returns:
            int: The number of pixels that have the exact same RGB value.
        """
        return sum(1 for p in pixels if p == rgb)

    # Sort by how common each color is (descending)
    filtered_colors.sort(key=color_count, reverse=True)

    # Convert to hex
    hex_colors = [f"{r:02x}{g:02x}{b:02x}" for r, g, b in filtered_colors]

    globs = Globs()

    if globs.debug["palette"]:
        await run_in_main_thread(debug_palette, hex_colors, palette)

    return hex_colors
