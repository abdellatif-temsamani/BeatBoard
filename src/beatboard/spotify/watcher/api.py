"""API wrapper – thin alias over WebSocket watcher."""

from __future__ import annotations

from .core import watch_spotify_websocket


async def watch_spotify_api(
    once: bool = False,
    reconnect_delay: float = 2.0,
    **kwargs,
) -> None:
    """Stream Spotify track changes and update hardware lighting."""
    if "poll_interval" in kwargs and kwargs["poll_interval"] is not None:
        try:
            reconnect_delay = float(kwargs["poll_interval"])
        except (TypeError, ValueError):
            pass
    await watch_spotify_websocket(once=once, reconnect_delay=reconnect_delay)


__all__ = ["watch_spotify_api"]
