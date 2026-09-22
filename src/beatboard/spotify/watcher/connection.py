"""WebSocket connection helpers – URL building and headers."""

from __future__ import annotations

import os
import urllib.parse

from ...globs import Globs
from ..constants import SPOTIFY_DEALER_WS_URL


_DEALER_HEADERS: dict[str, str] = {
    'Origin': 'https://open.spotify.com',
    'User-Agent': 'Mozilla/5.0 BeatBoard/0.3.0',
}


def _build_websocket_url(token: str) -> str:
    """Build the Spotify WebSocket (Dealer) URL."""
    globs = Globs()
    custom = getattr(globs, 'spotify_websocket_url', None) or os.getenv(
        'SPOTIFY_WEBSOCKET_URL'
    )
    if custom:
        custom = custom.strip()
        if custom:
            if '{token}' in custom:
                return custom.format(token=token)
            if 'access_token' not in custom:
                sep = '&' if '?' in custom else '?'
                return f'{custom}{sep}access_token={urllib.parse.quote(token, safe="")}'
            return custom
    return SPOTIFY_DEALER_WS_URL.format(token=urllib.parse.quote(token, safe=''))


def _resolve_websocket_url(token: str, websocket_url: str | None) -> str:
    """Resolve final WebSocket URL, handling custom overrides."""
    if websocket_url and '{token}' in websocket_url:
        return websocket_url.format(token=token)
    if (
        websocket_url
        and 'access_token' not in websocket_url
        and websocket_url.startswith('wss://')
    ):
        sep = '&' if '?' in websocket_url else '?'
        return f'{websocket_url}{sep}access_token={urllib.parse.quote(token, safe="")}'
    if websocket_url:
        return websocket_url
    return _build_websocket_url(token)


__all__ = ['_DEALER_HEADERS', '_build_websocket_url', '_resolve_websocket_url']
