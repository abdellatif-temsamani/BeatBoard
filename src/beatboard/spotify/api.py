"""Spotify REST API helpers – event-driven single GETs, no polling."""

from __future__ import annotations

import json
import time
from typing import Tuple

import requests

from ..logs import log
from .constants import SPOTIFY_CURRENTLY_PLAYING_URL, _UNAUTHORIZED
from .parsing import _extract_track_from_payload
from .session import _get_session


def _fetch_track_sync(
    track_id: str, token: str
) -> Tuple[str | None, str | None, str | None]:
    """Fetch a single track's (art_url, title, artist) via Spotify API."""
    t0 = time.perf_counter()
    try:
        sess = _get_session()
        resp = sess.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        dt = (time.perf_counter() - t0) * 1000
        _c = (
            "green"
            if resp.ok
            else "yellow"
            if resp.status_code in (204, 404)
            else "red"
        )
        log(
            "api",
            f"[cyan]api[/cyan] [dim]·[/dim] track [white]{track_id[:8]}…[/white] [{_c}]{resp.status_code}[/] [dim]·[/dim] [cyan]{dt:.0f}ms[/cyan]",
        )
        if resp.status_code == 401:
            return (None, None, None)
        if not resp.ok:
            return (None, None, None)
        data = resp.json()
        title = data.get("name")
        artists = data.get("artists") or []
        artist: str | None = None
        if artists:
            names = [
                a.get("name", "")
                for a in artists
                if isinstance(a, dict) and a.get("name")
            ]
            artist = ", ".join(n for n in names if n) if names else None
        art_url: str | None = None
        album = data.get("album") or {}
        if isinstance(album, dict):
            images = album.get("images") or []
            if images and isinstance(images[0], dict):
                art_url = images[0].get("url")
        return (art_url, title, artist)
    except requests.RequestException as exc:
        dt = (time.perf_counter() - t0) * 1000
        log(
            "api",
            f"[red]api[/red] [dim]·[/dim] track [white]{track_id[:8]}…[/white] [red]error[/red] [dim]·[/dim] [red]{dt:.0f}ms[/red] [dim]{exc}[/dim]",
        )
        return (None, None, None)


def _fetch_current_playback_sync(
    token: str,
) -> Tuple[str | None, str | None, str | None] | None | object:
    """Fetch currently playing track once – for initial hydration only."""
    t0 = time.perf_counter()
    log("api", "[cyan]api[/cyan] [dim]·[/dim] fetching now playing…")
    try:
        sess = _get_session()
        resp = sess.get(
            SPOTIFY_CURRENTLY_PLAYING_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        dt = (time.perf_counter() - t0) * 1000
        _c2 = (
            "green"
            if resp.status_code == 200
            else "yellow"
            if resp.status_code in (204, 404)
            else "red"
        )
        log(
            "api",
            f"[cyan]api[/cyan] [dim]·[/dim] now playing [{_c2}]{resp.status_code}[/] [dim]·[/dim] [cyan]{dt:.0f}ms[/cyan]",
        )
        if resp.status_code == 401:
            return _UNAUTHORIZED
        if resp.status_code == 204:
            return None
        if resp.status_code == 404:
            return None
        if not resp.ok:
            return None
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        extracted = _extract_track_from_payload(data)
        if extracted:
            return extracted
        if data.get("is_playing") is False:
            return None
        return None
    except requests.RequestException as exc:
        dt = (time.perf_counter() - t0) * 1000
        log(
            "api",
            f"[red]api[/red] [dim]·[/dim] now playing [red]error[/red] [dim]·[/dim] [red]{dt:.0f}ms[/red] [dim]{exc}[/dim]",
        )
        return None
