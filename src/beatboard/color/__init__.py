"""Color extraction package – facade re-exporting original flat API.

This package splits the original 640-line color_gen module into focused
submodules while preserving the ``beatboard.color`` import path via re-exports.

Layering:
  constants (leaf) → models / quantize (leaf) → palette → image (orchestrates)
"""

from __future__ import annotations

# --- constants ---
from .constants import (
    COLOR_CACHE_VERSION,
    RGB,
    RGBA,
    _FRACTION_BY_POPULATION,
    _RSHIFT,
    _SIG_BITS,
    _hex_to_rgb,
    _to_hex,
)

# --- models ---
from .models import Swatch, VibrantPalette, _GeneratorOptions

# --- quantize ---
from .quantize import (
    _Histogram,
    _PriorityQueue,
    _VBox,
    _default_filter,
    _split_boxes,
    quantize,
)

# --- palette ---
from .palette import (
    _comparison_value,
    _find_variation,
    _synthetic_swatch,
    generate_palette,
    select_argb_color,
)

# --- image ---
from .image import (
    _extract_vibrant,
    _load_pixels,
    debug_palette,
    extract_palette,
    get_color_palette,
    get_argb_color,
)

__all__ = [
    # types / constants
    "RGB",
    "RGBA",
    "_SIG_BITS",
    "_RSHIFT",
    "_FRACTION_BY_POPULATION",
    "COLOR_CACHE_VERSION",
    "_to_hex",
    "_hex_to_rgb",
    # models
    "Swatch",
    "VibrantPalette",
    "_GeneratorOptions",
    # quantize
    "_Histogram",
    "_VBox",
    "_PriorityQueue",
    "_default_filter",
    "_split_boxes",
    "quantize",
    # palette
    "_comparison_value",
    "_find_variation",
    "_synthetic_swatch",
    "generate_palette",
    "select_argb_color",
    # image
    "_load_pixels",
    "_extract_vibrant",
    "extract_palette",
    "debug_palette",
    "get_color_palette",
    "get_argb_color",
]
