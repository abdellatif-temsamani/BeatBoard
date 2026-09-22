"""Payload parsing helpers for Spotify WebSocket messages."""

from __future__ import annotations

import base64
import json
import re
from typing import Tuple


_TRACK_URI_RE = re.compile(r"spotify:track:([A-Za-z0-9]{22})")
_ART_URL_RE = re.compile(r"https://i\.scdn\.co/image/[A-Za-z0-9]+")
_SCDN_RE = re.compile(r'https://[^\s"\'"]*scdn\.co[^\s"\'"]*')
_SPOTIFYCDN_RE = re.compile(r'https://[^\s"\'\x00]*spotifycdn\.com[^\s"\'\x00]*')
_GENERIC_IMAGE_RE = re.compile(r'https://[^\s"\'\x00]+/image/[A-Za-z0-9]+')
_HTTPS_URL_RE = re.compile(r'https://[^\s"\'\x00]+')


def _extract_track_from_payload(
    data: object,
) -> Tuple[str | None, str | None, str | None] | None:
    """Extract (art_url, title, artist) from a WebSocket message payload.

    Handles several shapes:
      * Spotify REST ``currently-playing`` object (``{item: {...}}``)
      * Dealer ``cluster`` / ``player_state`` nesting
      * Generic ``payloads`` list wrapping the above
      * Simple ``{art_url, title, artist}`` push messages
    """

    if isinstance(data, dict) and "art_url" in data:
        return (
            data.get("art_url"),
            data.get("title"),
            data.get("artist"),
        )

    def _from_track_dict(
        track: dict,
    ) -> Tuple[str | None, str | None, str | None] | None:
        if not isinstance(track, dict):
            return None
        metadata = (
            track.get("metadata") if isinstance(track.get("metadata"), dict) else {}
        )
        title = track.get("name") or metadata.get("title") or track.get("title")
        artist: str | None = None
        if isinstance(track.get("artist_name"), str) and track.get("artist_name"):
            artist = track.get("artist_name")  # type: ignore[assignment]
        elif isinstance(metadata.get("artist_name"), str) and metadata.get(
            "artist_name"
        ):
            artist = metadata.get("artist_name")
        elif isinstance(track.get("artists"), list):
            names = [
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in track.get("artists", [])  # type: ignore[union-attr]
                if isinstance(a, (dict, str))
                and (a.get("name") if isinstance(a, dict) else a)
            ]
            artist = ", ".join(n for n in names if n) if names else None
        elif isinstance(track.get("artist"), dict) and track.get("artist", {}).get(
            "name"
        ):
            artist = track["artist"]["name"]  # type: ignore[index]
        art_url: str | None = None
        album = track.get("album")
        if isinstance(album, dict):
            images = album.get("images") or []
            if images and isinstance(images[0], dict) and images[0].get("url"):
                art_url = images[0].get("url")
        if not art_url and metadata:
            for key in (
                "image_xlarge_url",
                "image_large_url",
                "image_url",
                "image_small_url",
            ):
                val = metadata.get(key)
                if isinstance(val, str) and val.strip():
                    art_url = val.strip()
                    break
        if not art_url:
            for key in (
                "image_xlarge_url",
                "image_large_url",
                "image_url",
                "cover_url",
                "cover",
            ):
                val = track.get(key)
                if isinstance(val, str) and val.strip():
                    art_url = val.strip()
                    break
        if not art_url:
            for key in ("images",):
                val = track.get(key) or metadata.get(key)
                if (
                    isinstance(val, list)
                    and val
                    and isinstance(val[0], dict)
                    and val[0].get("url")
                ):
                    art_url = val[0].get("url")
                    break
        if art_url or title or artist:
            return (art_url, title, artist)
        return None

    stack: list[object] = [data]
    seen: set[int] = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))
        if isinstance(cur, dict):
            if "item" in cur and isinstance(cur["item"], dict):
                item = cur["item"]
                title = item.get("name")
                artists = item.get("artists") or []
                artist: str | None = None
                if artists:
                    names = [
                        a.get("name", "")
                        for a in artists
                        if isinstance(a, dict) and a.get("name")
                    ]
                    artist = ", ".join(n for n in names if n) if names else None
                album = item.get("album") or {}
                art_url: str | None = None
                if isinstance(album, dict):
                    images = album.get("images") or []
                    if images and isinstance(images[0], dict):
                        art_url = images[0].get("url")
                return (art_url, title, artist)

            if "track" in cur and isinstance(cur["track"], dict):
                extracted = _from_track_dict(cur["track"])
                if extracted:
                    return extracted

            if isinstance(cur.get("uri"), str) and cur["uri"].startswith(
                "spotify:track:"
            ):
                extracted = _from_track_dict(cur)
                if extracted:
                    return extracted

            for key in ("player_state", "cluster", "state", "result", "payload"):
                if key in cur and isinstance(cur[key], dict):
                    stack.append(cur[key])
            for key in ("payloads", "updates", "data", "clusters"):
                if key in cur and isinstance(cur[key], list):
                    stack.extend(cur[key])
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)

        elif isinstance(cur, list):
            stack.extend(cur)

    return None


def _parse_ws_message(
    raw: str | bytes,
) -> Tuple[str | None, str | None, str | None] | None:
    """Parse a raw WebSocket message into (art_url, title, artist)."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None
    raw = raw.strip()
    if not raw or raw in ("ping", "pong", '{"type":"ping"}', '{"type":"pong"}'):
        return None

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if isinstance(data, dict) and "payloads" in data:
        for p in data["payloads"]:
            if isinstance(p, str):
                try:
                    p_json = json.loads(p)
                    extracted = _extract_track_from_payload(p_json)
                    if extracted:
                        return extracted
                    p = p_json
                except json.JSONDecodeError:
                    pass
            if isinstance(p, (dict, list)):
                extracted = _extract_track_from_payload(p)
                if extracted:
                    return extracted
        return _extract_track_from_payload(data)

    return _extract_track_from_payload(data)


def _find_image_url(text: str) -> str | None:
    """Find first plausible Spotify image URL in text."""
    for pat in (_ART_URL_RE, _SCDN_RE, _SPOTIFYCDN_RE, _GENERIC_IMAGE_RE):
        m = pat.search(text)
        if m:
            url = m.group(0).strip().rstrip("\x00").rstrip('"').rstrip("'")
            m2 = _ART_URL_RE.search(url)
            if m2:
                return m2.group(0)
            return url.rstrip("/")
    for m in _HTTPS_URL_RE.finditer(text):
        url = m.group(0).strip().rstrip("\x00").rstrip('"').rstrip("'")
        low = url.lower()
        if "image" in low or "scdn" in low or "spotifycdn" in low:
            m2 = _ART_URL_RE.search(url)
            if m2:
                return m2.group(0)
            return url.split("\x12")[0].split("\x00")[0].rstrip("/")
    return None


def _extract_track_and_art_from_ws_raw(
    raw: str | bytes,
) -> tuple[str | None, str | None]:
    """Extract (track_id, art_url) from Dealer base64 payload if possible."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return (None, None)
    raw = raw.strip()
    if not raw:
        return (None, None)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = _TRACK_URI_RE.search(raw)
        art = _find_image_url(raw)
        return (m.group(1) if m else None, art)
    if not isinstance(data, dict):
        return (None, None)
    payloads = data.get("payloads")
    track_id: str | None = None
    art_url: str | None = None
    if isinstance(payloads, list):
        for p in payloads:
            if isinstance(p, str):
                m = _TRACK_URI_RE.search(p)
                if m and not track_id:
                    track_id = m.group(1)
                if not art_url:
                    art_url = _find_image_url(p)
                if track_id and art_url:
                    return (track_id, art_url)
                try:
                    padded = p + "=" * (-len(p) % 4)
                    decoded = base64.b64decode(padded, validate=False)
                    text = decoded.decode("utf-8", errors="ignore")
                    if not track_id:
                        m2 = _TRACK_URI_RE.search(text)
                        if m2:
                            track_id = m2.group(1)
                        else:
                            m3 = _TRACK_URI_RE.search(
                                decoded.decode("latin1", errors="ignore")
                            )
                            if m3:
                                track_id = m3.group(1)
                    if not art_url:
                        art_url = _find_image_url(text) or _find_image_url(
                            decoded.decode("latin1", errors="ignore")
                        )
                    if track_id and art_url:
                        return (track_id, art_url)
                except Exception:
                    continue
        if track_id or art_url:
            return (track_id, art_url)
    m = _TRACK_URI_RE.search(raw)
    art = _find_image_url(raw)
    return (m.group(1) if m else None, art)


def _extract_track_id_from_ws_raw(raw: str | bytes) -> str | None:
    """Extract a track id from a Dealer message where payloads are base64 protobuf."""
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None
    raw = raw.strip()
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        m = _TRACK_URI_RE.search(raw)
        return m.group(1) if m else None
    if not isinstance(data, dict):
        return None
    payloads = data.get("payloads")
    if isinstance(payloads, list):
        for p in payloads:
            if isinstance(p, str):
                m = _TRACK_URI_RE.search(p)
                if m:
                    return m.group(1)
                try:
                    padded = p + "=" * (-len(p) % 4)
                    decoded = base64.b64decode(padded, validate=False)
                    text = decoded.decode("utf-8", errors="ignore")
                    m2 = _TRACK_URI_RE.search(text)
                    if m2:
                        return m2.group(1)
                    m3 = _TRACK_URI_RE.search(decoded.decode("latin1", errors="ignore"))
                    if m3:
                        return m3.group(1)
                except Exception:
                    continue
    m = _TRACK_URI_RE.search(raw)
    return m.group(1) if m else None
