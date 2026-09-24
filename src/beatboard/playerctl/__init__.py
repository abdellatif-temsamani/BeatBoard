"""playerctl integration for BeatBoard.

Modular package split from the former ``playerctl.py`` monolith.
Public facade re-exports the original flat API for backward compatibility.

Layering:
  session / keys (leaf) → player / image (leaf) → apply (uses hardware)
  → process (orchestrates cache/palette/hardware) → watcher (orchestrates)
"""

from __future__ import annotations

from .apply import _run_hardware, apply_colors
from .image import get_image
from .keys import create_cache_key, create_track_cache_key
from .player import check_spotify_available, playerctl
from .process import process_art_url
from .session import _IMAGE_SESSION, _get_image_session
from .watcher import watch_playerctl

__all__ = [
    '_IMAGE_SESSION',
    '_get_image_session',
    'create_cache_key',
    'create_track_cache_key',
    'playerctl',
    'check_spotify_available',
    'get_image',
    'apply_colors',
    'process_art_url',
    'watch_playerctl',
    '_run_hardware',
]
