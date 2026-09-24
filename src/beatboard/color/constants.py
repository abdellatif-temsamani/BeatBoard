"""Constants and shared types for color extraction.

Layer: leaf – no internal dependencies.
"""

from __future__ import annotations

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]

_SIG_BITS = 5
_RSHIFT = 8 - _SIG_BITS
_FRACTION_BY_POPULATION = 0.75
COLOR_CACHE_VERSION = 'node-vibrant-v1'


def _to_hex(color: str | RGB) -> str:
    if isinstance(color, tuple):
        red, green, blue = color
        return f'{red:02x}{green:02x}{blue:02x}'
    return color.lstrip('#').lower()


def _hex_to_rgb(color: str) -> RGB:
    value = color.lstrip('#').lower()
    if len(value) == 3:
        value = ''.join(character * 2 for character in value)
    if len(value) != 6:
        raise ValueError(f'Invalid hex color: {color}')
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)
