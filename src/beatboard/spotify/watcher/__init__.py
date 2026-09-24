"""Spotify WebSocket watcher package – pure push via Dealer.

Facade preserving flat ``beatboard.spotify.watcher`` API.
Implementation split by responsibility:

- :mod:`connection` – WebSocket URL building and headers
- :mod:`hydration` – initial REST hydration (single GET, 401 refresh)
- :mod:`handlers` – per-message task factories
- :mod:`core` – reconnect loop and push dispatcher
- :mod:`api` – thin ``watch_spotify_api`` alias

This file re-exports the original flat API so both
``from beatboard.spotify import watch_spotify_websocket`` and
``from beatboard.spotify.watcher import watch_spotify_websocket`` keep working.
"""

from __future__ import annotations

from .api import watch_spotify_api
from .connection import _DEALER_HEADERS, _build_websocket_url, _resolve_websocket_url
from .core import watch_spotify_websocket
from .handlers import (
    _art_task,
    _bare_art_task,
    _cache_hit_task,
    _fetch_task,
    _parsed_task,
    _process_resolved_art,
)
from .hydration import _hydrate_initial

# Backwards compatibility aliases (mirrors beatboard.spotify)
watch_spotify = watch_spotify_api
watch_spotify_ws = watch_spotify_websocket

__all__ = [
    '_DEALER_HEADERS',
    '_build_websocket_url',
    '_resolve_websocket_url',
    'watch_spotify_websocket',
    'watch_spotify_api',
    'watch_spotify',
    'watch_spotify_ws',
    '_hydrate_initial',
    '_process_resolved_art',
    '_cache_hit_task',
    '_art_task',
    '_fetch_task',
    '_bare_art_task',
    '_parsed_task',
]
