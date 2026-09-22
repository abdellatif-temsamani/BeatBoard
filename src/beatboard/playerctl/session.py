"""Shared HTTP session for playerctl image downloads."""

from __future__ import annotations

_IMAGE_SESSION = None


def _get_image_session():
    global _IMAGE_SESSION
    if _IMAGE_SESSION is None:
        import requests

        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=10, max_retries=1
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({"User-Agent": "BeatBoard/0.3.0"})
        _IMAGE_SESSION = s
    return _IMAGE_SESSION
