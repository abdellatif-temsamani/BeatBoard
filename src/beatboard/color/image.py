"""Image loading and palette extraction."""

from __future__ import annotations

import time
from pathlib import Path

from PIL import Image, ImageOps
from rich import print
from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.text import Text

from ..globs import Globs
from .constants import RGB, RGBA, _hex_to_rgb, _to_hex
from .models import Swatch, VibrantPalette
from .palette import generate_palette, select_argb_color
from .quantize import quantize


def _load_pixels(
    path: str | Path, quality: int = 5
) -> tuple[list[RGBA], tuple[int, int]]:
    if quality < 1:
        raise ValueError('quality must be at least 1')

    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGBA')
        if quality > 1:
            width = max(1, image.width // quality)
            height = max(1, image.height // quality)
            image = image.resize((width, height), Image.Resampling.BILINEAR)
        return list(image.getdata()), image.size


def _extract_vibrant(
    path: str | Path, color_count: int = 64, quality: int = 5
) -> tuple[VibrantPalette, list[Swatch], tuple[int, int]]:
    pixels, size = _load_pixels(path, quality)
    swatches = quantize(pixels, color_count)
    return generate_palette(swatches), swatches, size


def extract_palette(path: str, color_count: int = 10) -> list[RGB]:
    """Extract raw MMCQ colors for palette debugging."""
    _, swatches, _ = _extract_vibrant(path, color_count=color_count)
    return [swatch.rgb for swatch in swatches]


def debug_palette(
    hex_colors: list[str] | None = None,
    palette: list[RGB] | None = None,
) -> None:
    """Print one or both color palettes in the terminal, with labels."""
    if hex_colors is None and palette is None:
        raise ValueError('You must pass either `hex_colors` or `palette`.')

    rows: list[tuple[str, list[str]]] = []
    if hex_colors:
        rows.append(('final colors', [_to_hex(color) for color in hex_colors]))
    if palette:
        rows.append(('quantized colors', [_to_hex(color) for color in palette]))
    if not rows:
        raise ValueError('At least one non-empty palette must be provided')

    console = Console()
    console.print('[bold]Palette debug[/bold]')
    for label, colors in rows:
        swatches_and_values = Text()
        for color in colors:
            try:
                red, green, blue = _hex_to_rgb(color)
                swatches_and_values.append(
                    '  ', style=Style(bgcolor=Color.from_rgb(red, green, blue))
                )
            except (TypeError, ValueError):
                pass
            swatches_and_values.append(f' #{color} ', style='dim')
        console.print(f'[bold cyan]{label:17}[/bold cyan]', swatches_and_values)


async def get_color_palette(path: str) -> list[str]:
    """Return node-vibrant-style palette colors for an image.

    The first color is the primary ``Vibrant`` swatch consumed by BeatBoard's
    hardware path. Remaining colors follow the dark-vibrant, light-vibrant,
    muted, dark-muted, and light-muted roles.
    """
    globs = Globs()
    start_time = time.perf_counter()
    palette, raw_swatches, size = _extract_vibrant(path)
    hex_colors = [swatch.hex for swatch in palette.swatches()]

    if globs.debug.get('perf') or globs.debug.get('all'):
        total_ms = (time.perf_counter() - start_time) * 1000
        print(
            f'[cyan]perf[/cyan] [dim]·[/dim] palette '
            f'[cyan]{total_ms:.0f}ms[/cyan] [dim]·[/dim] '
            f'{len(raw_swatches)}→{len(hex_colors)} colors [dim]·[/dim] '
            f'{size[0]}×{size[1]}'
        )

    if globs.debug.get('palette') or globs.debug.get('all'):
        debug_palette(hex_colors, [swatch.rgb for swatch in raw_swatches])

    return hex_colors


async def get_argb_color(path: str) -> str | None:
    """Return the best color from an image for ARGB lighting.

    Filters colors for visibility on LED lighting, prioritizing brightness
    and saturation over other factors.

    Args:
        path: Path to the image file.

    Returns:
        Hex color string suitable for ARGB, or None if no suitable color found.
    """
    globs = Globs()
    start_time = time.perf_counter()
    palette, raw_swatches, size = _extract_vibrant(path)
    argb_color = select_argb_color(palette)

    if globs.debug.get('perf') or globs.debug.get('all'):
        total_ms = (time.perf_counter() - start_time) * 1000
        print(
            f'[cyan]perf[/cyan] [dim]·[/dim] argb selection '
            f'[cyan]{total_ms:.0f}ms[/cyan] [dim]·[/dim] '
            f'{len(raw_swatches)} swatches [dim]·[/dim] '
            f'{size[0]}×{size[1]}'
        )

    if globs.debug.get('palette') or globs.debug.get('all'):
        debug_palette(
            [argb_color] if argb_color else None,
            [swatch.rgb for swatch in raw_swatches],
        )

    return argb_color
