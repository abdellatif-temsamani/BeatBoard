"""Cache key helpers for playerctl artwork."""

from __future__ import annotations

import hashlib

from ..color import COLOR_CACHE_VERSION


def create_cache_key(art_url: str) -> str:
    """Create a versioned cache key from an art URL.

    Args:
        art_url: The art URL to hash.

    Returns:
        A SHA256 hex digest suitable for use as a cache key.
    """
    value = f"{COLOR_CACHE_VERSION}\0{art_url}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_track_cache_key(track_id: str) -> str:
    """Namespace a Spotify track id by the active palette algorithm."""
    return f"{COLOR_CACHE_VERSION}:{track_id}"
