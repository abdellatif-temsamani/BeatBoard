import colorsys
from typing import List, Optional, Tuple

from colorthief import ColorThief
from PIL import Image
from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.text import Text

from .globs import Globs


def _to_hex(color: str | tuple[int, int, int]) -> str:
    if isinstance(color, tuple):
        r, g, b = color
        return f"{r:02x}{g:02x}{b:02x}"

    return color.lstrip("#").lower()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#").lower()

    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)

    if len(value) != 6:
        raise ValueError(f"Invalid hex color: {color}")

    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16))


def extract_palette(path: str, color_count: int = 10) -> list[Tuple[int, int, int]]:
    """Extract a raw RGB palette from an image file."""
    thief: ColorThief = ColorThief(path)
    return thief.get_palette(color_count=color_count)


def debug_palette(
    hex_colors: Optional[List[str]] = None,
    palette: Optional[List[Tuple[int, int, int]]] = None,
) -> None:
    """Print one or both color palettes in terminal, with labels.

    Args:
        hex_colors: A list of hex color codes without the # symbol.
        palette: A list of RGB color tuples (0-255).

    Raises:
        ValueError: If neither `hex_colors` nor `palette` is provided, or if all provided palettes are empty.
    """
    if hex_colors is None and palette is None:
        raise ValueError("You must pass either `hex_colors` or `palette`.")

    rows: list[tuple[str, list[str]]] = []

    if hex_colors:
        rows.append(("final colors", [_to_hex(c) for c in hex_colors]))

    if palette:
        rows.append(("extracted palette", [_to_hex(c) for c in palette]))

    if not rows:
        raise ValueError("At least one non-empty palette must be provided")

    console = Console()
    console.print("[bold]Palette debug[/bold]")

    for label, colors in rows:
        swatches_and_values = Text()
        for color in colors:
            r, g, b = _hex_to_rgb(color)
            swatches_and_values.append(
                "  ", style=Style(bgcolor=Color.from_rgb(r, g, b))
            )
            swatches_and_values.append(f" #{color} ", style="dim")

        console.print(f"[bold cyan]{label:17}[/bold cyan]", swatches_and_values)


async def get_color_palette(path: str) -> list[str]:
    """Get the color palette from the image

    Args:
        path: The path to the image to get the palette from.

    Returns:
        list[str]: A list of hex color codes without the # symbol.
    """
    palette: list[Tuple[int, int, int]] = extract_palette(path, color_count=10)

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
        debug_palette(hex_colors, palette)

    return hex_colors
