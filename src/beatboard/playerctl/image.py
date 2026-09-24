"""Album art fetching via playerctl / HTTP."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path

from .player import playerctl
from .session import _get_image_session


async def get_image(
    path: str,
    art_url: str | None = None,
) -> None:
    """Get the album art from the current playing song

    Args:
        path: The path to store the image temporarily
        art_url: The URL to the image. If not provided, it will be fetched from playerctl
    """
    if not art_url:
        url = await asyncio.to_thread(
            subprocess.run,
            playerctl('metadata', 'mpris:artUrl'),
            capture_output=True,
            text=True,
        )

        art_url = url.stdout.strip()

    if art_url.startswith('file://'):
        """just in case the image is local"""
        file_path = art_url[7:]
        image_data = await asyncio.to_thread(Path(file_path).read_bytes)
    else:
        # Use shared session with keep-alive – saves TCP+TLS handshake per track
        def _fetch():
            sess = _get_image_session()
            resp = sess.get(art_url, timeout=5)
            resp.raise_for_status()
            return resp.content

        image_data = await asyncio.to_thread(_fetch)

    # Write file asynchronously (thread)
    await asyncio.to_thread(Path(path).write_bytes, image_data)
