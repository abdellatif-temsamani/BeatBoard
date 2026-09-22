from __future__ import annotations

import hashlib

from beatboard.color import COLOR_CACHE_VERSION
from beatboard.playerctl import create_cache_key, create_track_cache_key


def test_palette_cache_key_is_versioned() -> None:
    art_url = "https://example.com/album.jpg"

    assert (
        create_cache_key(art_url)
        == hashlib.sha256(f"{COLOR_CACHE_VERSION}\0{art_url}".encode()).hexdigest()
    )
    assert create_cache_key(art_url) != hashlib.sha256(art_url.encode()).hexdigest()


def test_track_cache_key_is_versioned() -> None:
    assert create_track_cache_key("spotify:track:123") == (
        f"{COLOR_CACHE_VERSION}:spotify:track:123"
    )
