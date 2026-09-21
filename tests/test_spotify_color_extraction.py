"""Tests for the node-vibrant-compatible color extraction pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from beatboard.color_gen import (
    Swatch,
    extract_palette,
    generate_palette,
    get_color_palette,
    quantize,
)


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """Create a lossless image with red, green, and blue regions."""
    path = tmp_path / "sample.png"
    image = Image.new("RGB", (100, 100), "blue")
    for x in range(50):
        for y in range(50):
            image.putpixel((x, y), (255, 0, 0))
    for x in range(50, 100):
        for y in range(50):
            image.putpixel((x, y), (0, 255, 0))
    image.save(path)
    return path


def test_quantize_rejects_transparent_and_near_white_pixels() -> None:
    pixels = (
        [(255, 255, 255, 255)] * 20 + [(0, 0, 255, 124)] * 20 + [(255, 0, 0, 255)] * 10
    )

    swatches = quantize(pixels, color_count=8)

    assert [(swatch.rgb, swatch.population) for swatch in swatches] == [
        ((252, 4, 4), 10)
    ]


def test_quantize_tracks_population() -> None:
    pixels = [(255, 0, 0, 255)] * 30 + [(0, 255, 0, 255)] * 20 + [(0, 0, 255, 255)] * 10

    swatches = quantize(pixels, color_count=8)

    assert sum(swatch.population for swatch in swatches) == len(pixels)
    assert {swatch.rgb for swatch in swatches} == {
        (252, 4, 4),
        (4, 252, 4),
        (4, 4, 252),
    }


@pytest.mark.parametrize("color_count", [0, 1, 257])
def test_quantize_validates_color_count(color_count: int) -> None:
    with pytest.raises(ValueError, match="between 2 and 256"):
        quantize([(255, 0, 0, 255)], color_count=color_count)


def test_generator_selects_named_variations() -> None:
    swatches = [
        Swatch((220, 30, 30), 50),
        Swatch((80, 10, 10), 40),
        Swatch((250, 150, 150), 30),
        Swatch((130, 110, 110), 20),
        Swatch((60, 50, 50), 10),
        Swatch((220, 205, 205), 5),
    ]

    palette = generate_palette(swatches)

    assert palette.vibrant is swatches[0]
    assert palette.dark_vibrant is swatches[1]
    assert palette.light_vibrant is swatches[2]
    assert palette.muted is swatches[3]
    assert palette.dark_muted is swatches[4]
    assert palette.light_muted is swatches[5]


def test_generator_synthesizes_missing_vibrant_roles() -> None:
    palette = generate_palette([Swatch((252, 4, 4), 100)])

    assert palette.vibrant is not None
    assert palette.vibrant.rgb == (252, 4, 4)
    assert palette.dark_vibrant is not None
    assert palette.dark_vibrant.population == 0
    assert palette.light_vibrant is not None
    assert palette.light_vibrant.population == 0


def test_generator_promotes_a_muted_palette() -> None:
    palette = generate_palette([Swatch((50, 50, 50), 100)])

    assert palette.vibrant is not None
    assert palette.dark_vibrant is not None
    assert palette.light_vibrant is not None


def test_extract_palette_uses_mmcq(sample_image: Path) -> None:
    colors = extract_palette(str(sample_image), color_count=8)

    for expected in ((255, 0, 0), (0, 255, 0), (0, 0, 255)):
        assert any(
            max(abs(actual - target) for actual, target in zip(color, expected)) < 12
            for color in colors
        )


@pytest.mark.asyncio
async def test_get_color_palette_returns_vibrant_role_first(
    sample_image: Path,
) -> None:
    colors = await get_color_palette(str(sample_image))

    assert colors
    assert colors[0] in {"fc0404", "04fc04", "0404fc"}
    assert len(colors) == len(set(colors))
    assert all(len(color) == 6 for color in colors)
    assert all(set(color) <= set("0123456789abcdef") for color in colors)


@pytest.mark.asyncio
async def test_get_color_palette_ignores_all_white_image(tmp_path: Path) -> None:
    path = tmp_path / "white.png"
    Image.new("RGB", (20, 20), "white").save(path)

    assert await get_color_palette(str(path)) == []
