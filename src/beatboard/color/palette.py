"""Palette generation – classification of MMCQ swatches."""

from __future__ import annotations

import colorsys
from typing import Sequence

from .models import Swatch, VibrantPalette, _GeneratorOptions


def _is_argb_suitable(swatch: Swatch) -> bool:
    """Check if a swatch is suitable for ARGB lighting.
    
    ARGB LEDs need colors with sufficient brightness and saturation to be visible.
    Very dark colors (lightness < 0.15) or very desaturated colors don't show well.
    
    Args:
        swatch: The color swatch to evaluate.
        
    Returns:
        True if the color is suitable for ARGB lighting.
    """
    _, saturation, lightness = swatch.hsl
    # Filter out very dark colors and very desaturated colors
    # Lightness threshold: 0.15 (avoid nearly black colors)
    # Saturation threshold: 0.1 (avoid nearly gray colors)
    return lightness >= 0.15 and saturation >= 0.1


def select_argb_color(palette: VibrantPalette) -> str | None:
    """Select the best color from a palette for ARGB lighting.
    
    Prioritizes vibrant colors that will show well on LED lighting.
    Falls back through the palette in order of preference.
    
    Args:
        palette: The vibrant palette to select from.
        
    Returns:
        Hex color string suitable for ARGB, or None if no suitable color found.
    """
    # Try vibrant first (most visible), then light_vibrant, then others
    preference_order = [
        palette.vibrant,
        palette.light_vibrant,
        palette.light_muted,
        palette.muted,
        palette.dark_vibrant,
        palette.dark_muted,
    ]
    
    for swatch in preference_order:
        if swatch is not None and _is_argb_suitable(swatch):
            return swatch.hex
    
    # If no swatch passes the filter, return the first available color as fallback
    for swatch in preference_order:
        if swatch is not None:
            return swatch.hex
    
    return None


def _comparison_value(
    saturation: float,
    target_saturation: float,
    luma: float,
    target_luma: float,
    population: int,
    max_population: int,
    options: _GeneratorOptions,
) -> float:
    values = (
        (1 - abs(saturation - target_saturation), options.weight_saturation),
        (1 - abs(luma - target_luma), options.weight_luma),
        (population / max_population, options.weight_population),
    )
    included = [(value, weight) for value, weight in values if value and weight]
    return sum(value * weight for value, weight in included) / sum(
        weight for _, weight in included
    )


def _find_variation(
    selected: Sequence[Swatch | None],
    swatches: Sequence[Swatch],
    max_population: int,
    target_luma: float,
    min_luma: float,
    max_luma: float,
    target_saturation: float,
    min_saturation: float,
    max_saturation: float,
    options: _GeneratorOptions,
) -> Swatch | None:
    best: Swatch | None = None
    best_value = 0.0
    for swatch in swatches:
        _, saturation, luma = swatch.hsl
        if (
            min_saturation <= saturation <= max_saturation
            and min_luma <= luma <= max_luma
            and all(swatch is not item for item in selected)
        ):
            value = _comparison_value(
                saturation,
                target_saturation,
                luma,
                target_luma,
                swatch.population,
                max_population,
                options,
            )
            if best is None or value > best_value:
                best = swatch
                best_value = value
    return best


def _synthetic_swatch(source: Swatch, lightness: float) -> Swatch:
    hue, saturation, _ = source.hsl
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return Swatch(
        (int(red * 255), int(green * 255), int(blue * 255)),
        population=0,
    )


def generate_palette(swatches: Sequence[Swatch]) -> VibrantPalette:
    """Classify MMCQ swatches with node-vibrant's default generator."""
    if not swatches:
        return VibrantPalette()

    options = _GeneratorOptions()
    max_population = max(swatch.population for swatch in swatches)
    selected: list[Swatch | None] = []

    def find(
        target_luma: float,
        min_luma: float,
        max_luma: float,
        target_saturation: float,
        min_saturation: float,
        max_saturation: float,
    ) -> Swatch | None:
        swatch = _find_variation(
            selected,
            swatches,
            max_population,
            target_luma,
            min_luma,
            max_luma,
            target_saturation,
            min_saturation,
            max_saturation,
            options,
        )
        selected.append(swatch)
        return swatch

    vibrant = find(
        options.target_normal_luma,
        options.min_normal_luma,
        options.max_normal_luma,
        options.target_vibrant_saturation,
        options.min_vibrant_saturation,
        1,
    )
    light_vibrant = find(
        options.target_light_luma,
        options.min_light_luma,
        1,
        options.target_vibrant_saturation,
        options.min_vibrant_saturation,
        1,
    )
    dark_vibrant = find(
        options.target_dark_luma,
        0,
        options.max_dark_luma,
        options.target_vibrant_saturation,
        options.min_vibrant_saturation,
        1,
    )
    muted = find(
        options.target_normal_luma,
        options.min_normal_luma,
        options.max_normal_luma,
        options.target_muted_saturation,
        0,
        options.max_muted_saturation,
    )
    light_muted = find(
        options.target_light_luma,
        options.min_light_luma,
        1,
        options.target_muted_saturation,
        0,
        options.max_muted_saturation,
    )
    dark_muted = find(
        options.target_dark_luma,
        0,
        options.max_dark_luma,
        options.target_muted_saturation,
        0,
        options.max_muted_saturation,
    )

    # Synthetic fallbacks disabled — only return colors that exist in the artwork.
    # Previously this mirrored node-vibrant's _synthetic_swatch logic (creating
    # new colors by shifting lightness/saturation when a role was missing).
    # Per user request, we now keep only quantized swatches from the image;
    # missing roles stay None and are omitted from palette.swatches().
    pass

    return VibrantPalette(
        vibrant=vibrant,
        dark_vibrant=dark_vibrant,
        light_vibrant=light_vibrant,
        muted=muted,
        dark_muted=dark_muted,
        light_muted=light_muted,
    )
