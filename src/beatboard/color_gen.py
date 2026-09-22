"""Color extraction inspired by node-vibrant.

Palette generation follows similar quantization (modified median-cut) and
palette-selection ideas as https://github.com/Vibrant-Colors/node-vibrant
(MIT License, Copyright (c) 2015 Jari Zwarts and AKFish), but this is an
original implementation that does not contain code copied from that project.

Deprecated: use ``beatboard.color`` instead. This shim re-exports the
original public API for backward compatibility and will be removed in a
future release.
"""

from __future__ import annotations

# Re-export everything from the new modular package.
# Keep explicit imports for ruff / type-checkers and to preserve identity.
from .color import (  # noqa: F401
    COLOR_CACHE_VERSION,
    RGB,
    RGBA,
    Swatch,
    VibrantPalette,
    _FRACTION_BY_POPULATION,
    _GeneratorOptions,
    _Histogram,
    _PriorityQueue,
    _RSHIFT,
    _SIG_BITS,
    _VBox,
    _comparison_value,
    _default_filter,
    _extract_vibrant,
    _find_variation,
    _hex_to_rgb,
    _load_pixels,
    _split_boxes,
    _synthetic_swatch,
    _to_hex,
    debug_palette,
    extract_palette,
    generate_palette,
    get_color_palette,
    quantize,
)

__all__ = [
    "RGB",
    "RGBA",
    "_SIG_BITS",
    "_RSHIFT",
    "_FRACTION_BY_POPULATION",
    "COLOR_CACHE_VERSION",
    "_to_hex",
    "_hex_to_rgb",
    "Swatch",
    "VibrantPalette",
    "_GeneratorOptions",
    "_Histogram",
    "_VBox",
    "_PriorityQueue",
    "_default_filter",
    "_split_boxes",
    "quantize",
    "_comparison_value",
    "_find_variation",
    "_synthetic_swatch",
    "generate_palette",
    "_load_pixels",
    "_extract_vibrant",
    "extract_palette",
    "debug_palette",
    "get_color_palette",
]
