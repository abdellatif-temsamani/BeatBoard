"""Dataclasses for color swatches and palettes."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import Iterator

from .constants import RGB, _to_hex


@dataclass(eq=False, frozen=True)
class Swatch:
    """A quantized color and the number of source pixels it represents."""

    rgb: RGB
    population: int

    @property
    def hsl(self) -> tuple[float, float, float]:
        """Return hue, saturation, and lightness in the 0..1 range."""
        hue, lightness, saturation = colorsys.rgb_to_hls(
            *(channel / 255 for channel in self.rgb)
        )
        return hue, saturation, lightness

    @property
    def hex(self) -> str:
        """Return a six-character lowercase hex color without a prefix."""
        return _to_hex(self.rgb)


@dataclass(frozen=True)
class VibrantPalette:
    """The six color roles produced by node-vibrant's default generator."""

    vibrant: Swatch | None = None
    dark_vibrant: Swatch | None = None
    light_vibrant: Swatch | None = None
    muted: Swatch | None = None
    dark_muted: Swatch | None = None
    light_muted: Swatch | None = None

    def swatches(self) -> Iterator[Swatch]:
        """Yield distinct swatches in node-vibrant's primary-role order."""
        seen: set[RGB] = set()
        for swatch in (
            self.vibrant,
            self.dark_vibrant,
            self.light_vibrant,
            self.muted,
            self.dark_muted,
            self.light_muted,
        ):
            if swatch is not None and swatch.rgb not in seen:
                seen.add(swatch.rgb)
                yield swatch


@dataclass(frozen=True)
class _GeneratorOptions:
    target_dark_luma: float = 0.26
    max_dark_luma: float = 0.45
    min_light_luma: float = 0.55
    target_light_luma: float = 0.74
    min_normal_luma: float = 0.3
    target_normal_luma: float = 0.5
    max_normal_luma: float = 0.7
    target_muted_saturation: float = 0.3
    max_muted_saturation: float = 0.4
    target_vibrant_saturation: float = 1.0
    min_vibrant_saturation: float = 0.35
    weight_saturation: float = 3
    weight_luma: float = 6.5
    weight_population: float = 0.5
