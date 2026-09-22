"""Shared HTTP session for Spotify API.

Reusing a single ``requests.Session`` avoids per-request TCP+TLS handshake
(saves 50-150ms on Spotify API and image downloads). Mounted adapter keeps
10 pooled connections.
"""

from __future__ import annotations

import requests

_SESSION: requests.Session | None = None


def _get_session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=10, max_retries=1
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({"User-Agent": "BeatBoard/0.3.0 (spotify-websocket)"})
        _SESSION = s
    return _SESSION
