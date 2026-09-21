import colorsys
import time
from typing import List, Optional, Tuple

import numpy as np
from colorthief import ColorThief
from rich import print
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


def calculate_colorfulness(rgb_tuple: Tuple[int, int, int]) -> float:
    """Calculate the colorfulness of a single color using Hasler & Süsstrunk metric.

    Args:
        rgb_tuple: RGB color tuple (0-255)

    Returns:
        float: Colorfulness score (higher = more colorful)
    """
    r, g, b = rgb_tuple

    # Convert to float for calculations
    r, g, b = float(r), float(g), float(b)

    # Opponent color space representation
    rg = abs(r - g)
    yb = abs(0.5 * (r + g) - b)

    # For a single color, the std dev is 0, so we only use the mean
    mean_root = (rg**2 + yb**2) ** 0.5

    # Colorfulness metric (simplified for single color)
    return mean_root


def calculate_lightness(rgb_tuple: Tuple[int, int, int]) -> float:
    """Calculate the lightness of a color (0.0 = dark, 1.0 = light).

    Args:
        rgb_tuple: RGB color tuple (0-255)

    Returns:
        float: Lightness value (0.0-1.0)
    """
    r, g, b = rgb_tuple
    _, lightness, _ = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    return lightness


def kmeans_colors(pixels: np.ndarray, n_clusters: int = 8) -> np.ndarray:
    """Perform K-means clustering to find dominant colors.

    Args:
        pixels: Array of RGB pixels (N x 3)
        n_clusters: Number of clusters to find

    Returns:
        np.ndarray: Array of cluster centers (RGB values)
    """
    from sklearn.cluster import KMeans

    # Reshape pixels for sklearn
    pixels_reshaped = pixels.reshape(-1, 3)

    # Perform K-means clustering with fewer iterations for speed
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=3, max_iter=50)
    kmeans.fit(pixels_reshaped)

    # Get cluster centers (dominant colors)
    colors = kmeans.cluster_centers_.astype(int)

    return colors


def calculate_color_percentage(
    pixels: np.ndarray, target_color: Tuple[int, int, int], tolerance: int = 30
) -> float:
    """Calculate the percentage of pixels that match a target color within tolerance.

    Args:
        pixels: Array of RGB pixels (N x 3)
        target_color: RGB color tuple to match against
        tolerance: Color distance tolerance (0-255)

    Returns:
        float: Percentage of pixels matching (0.0-1.0)
    """
    if len(pixels) == 0:
        return 0.0

    # Calculate Euclidean distance to target color
    distances = np.sqrt(np.sum((pixels - target_color) ** 2, axis=1))

    # Count pixels within tolerance
    matching_pixels = np.sum(distances <= tolerance)

    return matching_pixels / len(pixels)


def spotify_score_color(
    rgb_tuple: Tuple[int, int, int],
    colorfulness: float,
    lightness: float,
    percentage: float,
    colorfulness_weight: float = 1.0,
    darkness_weight: float = 0.8,
    area_weight: float = 0.5,
) -> float:
    """Calculate Spotify-style score for a color.

    Spotify's algorithm prioritizes:
    1. Colorfulness (vivid colors preferred)
    2. Darkness (darker colors preferred for background)
    3. Area (colors that occupy more of the image)

    Args:
        rgb_tuple: RGB color tuple (0-255)
        colorfulness: Colorfulness score
        lightness: Lightness value (0.0-1.0)
        percentage: Percentage of image area
        colorfulness_weight: Weight for colorfulness factor
        darkness_weight: Weight for darkness factor
        area_weight: Weight for area factor

    Returns:
        float: Combined score (higher = better background color)
    """
    # Normalize colorfulness (typical range 0-100)
    normalized_colorfulness = min(colorfulness / 100.0, 1.0)

    # Darkness score (inverted lightness - darker is better)
    darkness_score = 1.0 - lightness

    # Area is already normalized (0.0-1.0)

    # Combined weighted score
    score = (
        normalized_colorfulness * colorfulness_weight
        + darkness_score * darkness_weight
        + percentage * area_weight
    )

    return score


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
            try:
                r, g, b = _hex_to_rgb(color)
                swatches_and_values.append(
                    "  ", style=Style(bgcolor=Color.from_rgb(r, g, b))
                )
            except Exception:
                # If color swatch fails, just show the hex value
                pass
            swatches_and_values.append(f" #{color} ", style="dim")

        console.print(f"[bold cyan]{label:17}[/bold cyan]", swatches_and_values)


async def get_color_palette(path: str) -> list[str]:
    """Get the color palette from the image using Spotify-style algorithm.

    Args:
        path: The path to the image to get the palette from.

    Returns:
        list[str]: A list of hex color codes without the # symbol, sorted by Spotify-style scoring.
    """
    globs = Globs()
    start_time = time.time()

    # Use ColorThief for fast color extraction
    thief_start = time.time()
    thief = ColorThief(path)
    palette = thief.get_palette(color_count=8)
    thief_time = time.time() - thief_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[bold cyan]PERF:[/bold cyan] ColorThief extraction: {thief_time:.3f}s")

    # Load image for pixel analysis
    img_load_start = time.time()
    img = Image.open(path).convert("RGB")

    # Resize to max 64x64 for faster processing
    max_size = 64
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    img_array = np.array(img)
    pixels = img_array.reshape(-1, 3)
    img_load_time = time.time() - img_load_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        print(
            f"[bold cyan]PERF:[/bold cyan] Image loading for analysis: {img_load_time:.3f}s"
        )

    # Calculate scores for each color
    scoring_start = time.time()
    scored_colors = []

    for color in palette:
        rgb_tuple = tuple(color)

        # Calculate colorfulness
        colorfulness = calculate_colorfulness(rgb_tuple)

        # Calculate lightness
        lightness = calculate_lightness(rgb_tuple)

        # Calculate percentage of image area
        percentage = calculate_color_percentage(pixels, rgb_tuple, tolerance=30)

        # Calculate Spotify-style score
        score = spotify_score_color(rgb_tuple, colorfulness, lightness, percentage)

        scored_colors.append((rgb_tuple, score, colorfulness, lightness, percentage))

    scoring_time = time.time() - scoring_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[bold cyan]PERF:[/bold cyan] Color scoring: {scoring_time:.3f}s")

    # Sort by score (descending)
    sort_start = time.time()
    scored_colors.sort(key=lambda x: x[1], reverse=True)
    sort_time = time.time() - sort_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[bold cyan]PERF:[/bold cyan] Sorting: {sort_time:.3f}s")

    # Filter out colors that are too neutral or too bright
    filter_start = time.time()
    filtered_colors = []
    for rgb_tuple, score, colorfulness, lightness, percentage in scored_colors:
        _, _, saturation = colorsys.rgb_to_hls(
            rgb_tuple[0] / 255, rgb_tuple[1] / 255, rgb_tuple[2] / 255
        )

        # Skip neutral colors and very bright colors
        if saturation < 0.15 or lightness > 0.9:
            continue

        filtered_colors.append(rgb_tuple)
    filter_time = time.time() - filter_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[bold cyan]PERF:[/bold cyan] Color filtering: {filter_time:.3f}s")

    # Fallback if all colors are filtered
    if not filtered_colors:
        filtered_colors = [rgb_tuple for rgb_tuple, _, _, _, _ in scored_colors[:3]]

    # Convert to hex
    hex_start = time.time()
    hex_colors = [f"{r:02x}{g:02x}{b:02x}" for r, g, b in filtered_colors]
    hex_time = time.time() - hex_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[bold cyan]PERF:[/bold cyan] Hex conversion: {hex_time:.3f}s")

    total_time = time.time() - start_time
    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[bold cyan]PERF:[/bold cyan] Total time: {total_time:.3f}s")
        print(f"[bold cyan]PERF:[/bold cyan] Image dimensions: {img_array.shape}")
        print(f"[bold cyan]PERF:[/bold cyan] Colors found: {len(palette)}")
        print(
            f"[bold cyan]PERF:[/bold cyan] Colors after filtering: {len(filtered_colors)}"
        )

    if globs.debug.get("palette") or globs.debug.get("all"):
        debug_palette(hex_colors, palette)

    return hex_colors
