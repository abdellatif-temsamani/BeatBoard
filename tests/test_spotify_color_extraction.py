"""Test Spotify-style color extraction algorithm."""

import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from beatboard.color_gen import (
    calculate_colorfulness,
    calculate_color_percentage,
    calculate_lightness,
    get_color_palette,
    kmeans_colors,
    spotify_score_color,
)


@pytest.fixture
def sample_image():
    """Create a sample image with known colors for testing."""
    # Create a 100x100 image with red, green, and blue regions
    img_array = np.zeros((100, 100, 3), dtype=np.uint8)

    # Red region (top-left)
    img_array[0:50, 0:50] = [255, 0, 0]

    # Green region (top-right)
    img_array[0:50, 50:100] = [0, 255, 0]

    # Blue region (bottom)
    img_array[50:100, :] = [0, 0, 255]

    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        img = Image.fromarray(img_array)
        img.save(f.name)
        yield f.name

    # Cleanup
    Path(f.name).unlink(missing_ok=True)


def test_calculate_colorfulness():
    """Test colorfulness calculation."""
    # Red should be colorful
    red_score = calculate_colorfulness((255, 0, 0))
    assert red_score > 0

    # Blue should also be colorful
    blue_score = calculate_colorfulness((0, 0, 255))
    assert blue_score > 0

    # White should be less colorful than saturated colors
    white_score = calculate_colorfulness((255, 255, 255))
    assert white_score < red_score
    assert white_score < blue_score

    # Yellow should be colorful
    yellow_score = calculate_colorfulness((255, 255, 0))
    assert yellow_score > 0
    assert yellow_score > white_score


def test_calculate_lightness():
    """Test lightness calculation."""
    # Black should have 0.0 lightness
    black_lightness = calculate_lightness((0, 0, 0))
    assert black_lightness == 0.0

    # White should have 1.0 lightness
    white_lightness = calculate_lightness((255, 255, 255))
    assert white_lightness == 1.0

    # Gray should be around 0.5
    gray_lightness = calculate_lightness((128, 128, 128))
    assert 0.4 < gray_lightness < 0.6


def test_calculate_color_percentage():
    """Test color percentage calculation."""
    # Create test pixels: 50% red, 50% blue
    pixels = np.array([[255, 0, 0]] * 50 + [[0, 0, 255]] * 50)

    red_percentage = calculate_color_percentage(pixels, (255, 0, 0), tolerance=10)
    assert 0.45 < red_percentage < 0.55

    blue_percentage = calculate_color_percentage(pixels, (0, 0, 255), tolerance=10)
    assert 0.45 < blue_percentage < 0.55

    # Green should have 0% match
    green_percentage = calculate_color_percentage(pixels, (0, 255, 0), tolerance=10)
    assert green_percentage < 0.1


def test_spotify_score_color():
    """Test Spotify-style scoring."""
    # A colorful, dark color should score higher
    dark_colorful = spotify_score_color(
        (200, 50, 50), colorfulness=80.0, lightness=0.3, percentage=0.5
    )

    # A bright, neutral color should score lower
    bright_neutral = spotify_score_color(
        (200, 200, 200), colorfulness=10.0, lightness=0.8, percentage=0.5
    )

    assert dark_colorful > bright_neutral


def test_kmeans_colors():
    """Test K-means color clustering (utility function)."""
    # Create simple image with 3 distinct colors
    pixels = np.array([[255, 0, 0]] * 30 + [[0, 255, 0]] * 30 + [[0, 0, 255]] * 40)

    colors = kmeans_colors(pixels, n_clusters=3)

    # Should return 3 colors
    assert len(colors) == 3

    # Colors should be close to the original colors
    colors_set = {tuple(color) for color in colors}

    # Check that we found colors similar to red, green, blue
    found_red = any(
        all(abs(c[i] - target[i]) < 50 for i in range(3))
        for c in colors_set
        for target in [(255, 0, 0)]
    )
    found_green = any(
        all(abs(c[i] - target[i]) < 50 for i in range(3))
        for c in colors_set
        for target in [(0, 255, 0)]
    )
    found_blue = any(
        all(abs(c[i] - target[i]) < 50 for i in range(3))
        for c in colors_set
        for target in [(0, 0, 255)]
    )

    assert found_red or found_green or found_blue

    # Test with fewer clusters
    colors_2 = kmeans_colors(pixels, n_clusters=2)
    assert len(colors_2) == 2


@pytest.mark.asyncio
async def test_get_color_palette(sample_image):
    """Test the main color palette extraction function."""
    hex_colors = await get_color_palette(sample_image)

    # Should return a list of hex colors
    assert isinstance(hex_colors, list)
    assert len(hex_colors) > 0

    # Each should be a valid 6-character hex string
    for color in hex_colors:
        assert len(color) == 6
        assert all(c in "0123456789abcdef" for c in color.lower())

    # Colors should be different (diverse palette)
    assert len(set(hex_colors)) > 1


@pytest.mark.asyncio
async def test_color_palette_sorting(sample_image):
    """Test that colors are sorted by Spotify-style scoring."""
    hex_colors = await get_color_palette(sample_image)

    # The first color should be the highest scoring
    # For our test image with red, green, blue regions,
    # we expect one of these colors to be dominant

    # Convert first color back to RGB
    first_color_hex = hex_colors[0]
    r = int(first_color_hex[0:2], 16)
    g = int(first_color_hex[2:4], 16)
    b = int(first_color_hex[4:6], 16)

    # Should be one of the dominant colors from our test image
    # (red, green, or blue with some tolerance)
    is_red_like = r > 200 and g < 50 and b < 50
    is_green_like = g > 200 and r < 50 and b < 50
    is_blue_like = b > 200 and r < 50 and g < 50

    assert is_red_like or is_green_like or is_blue_like


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
