"""Spotify WebSocket integration for BeatBoard.

This module provides an alternative to ``playerctl`` for platforms where
``playerctl`` is unavailable. When the ``--api`` (alias ``--spotify``) flag
is used, BeatBoard authenticates with the user's Spotify account and uses
a Spotify WebSocket (Dealer) connection for real-time track change
notifications – pure push, no REST polling.

Authentication resolution and Dealer transport are implemented in
submodules of this package; this file is the public facade re-exporting
the original flat API for backward compatibility.
"""

from __future__ import annotations

# --- constants ---
from .constants import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPES,
    SPOTIFY_AUTH_URL,
    SPOTIFY_CURRENTLY_PLAYING_URL,
    SPOTIFY_DEALER_WS_URL,
    SPOTIFY_TOKEN_URL,
    _UNAUTHORIZED,
)

# --- session ---
from .session import _SESSION, _get_session

# --- auth / tokens ---
from .auth import (
    _try_client_credentials_token,
    _try_refresh_token,
    build_auth_url,
    check_spotify_api_available,
    ensure_valid_token,
    exchange_code_for_token,
    get_spotify_token,
    refresh_access_token,
    run_oauth_flow,
    save_spotify_tokens,
)

# --- callback server ---
from .callback import _CallbackHandler, _run_local_server

# --- parsing helpers ---
from .parsing import (
    _ART_URL_RE,
    _GENERIC_IMAGE_RE,
    _HTTPS_URL_RE,
    _SCDN_RE,
    _SPOTIFYCDN_RE,
    _TRACK_URI_RE,
    _extract_track_and_art_from_ws_raw,
    _extract_track_from_payload,
    _extract_track_id_from_ws_raw,
    _find_image_url,
    _parse_ws_message,
)

# --- API client ---
from .api import _fetch_current_playback_sync, _fetch_track_sync

# --- watcher ---
from .watcher import (
    _build_websocket_url,
    watch_spotify_api,
    watch_spotify_websocket,
)

# Backwards compatibility aliases
watch_spotify = watch_spotify_api
watch_spotify_ws = watch_spotify_websocket
check_spotify_available_api = check_spotify_api_available
get_token = get_spotify_token

__all__ = [
    # constants
    'SPOTIFY_TOKEN_URL',
    'SPOTIFY_AUTH_URL',
    'DEFAULT_SCOPES',
    'DEFAULT_REDIRECT_URI',
    'SPOTIFY_DEALER_WS_URL',
    'SPOTIFY_CURRENTLY_PLAYING_URL',
    'DEFAULT_CLIENT_ID',
    'DEFAULT_CLIENT_SECRET',
    '_UNAUTHORIZED',
    # session
    '_SESSION',
    '_get_session',
    # auth
    'get_spotify_token',
    '_try_client_credentials_token',
    'build_auth_url',
    'exchange_code_for_token',
    'refresh_access_token',
    'save_spotify_tokens',
    '_CallbackHandler',
    '_run_local_server',
    'run_oauth_flow',
    '_try_refresh_token',
    'ensure_valid_token',
    'check_spotify_api_available',
    # websocket / parsing
    '_build_websocket_url',
    '_extract_track_from_payload',
    '_parse_ws_message',
    '_TRACK_URI_RE',
    '_ART_URL_RE',
    '_SCDN_RE',
    '_SPOTIFYCDN_RE',
    '_GENERIC_IMAGE_RE',
    '_HTTPS_URL_RE',
    '_find_image_url',
    '_extract_track_and_art_from_ws_raw',
    '_extract_track_id_from_ws_raw',
    # api
    '_fetch_track_sync',
    '_fetch_current_playback_sync',
    # watcher
    'watch_spotify_websocket',
    'watch_spotify_api',
    # aliases
    'watch_spotify',
    'watch_spotify_ws',
    'check_spotify_available_api',
    'get_token',
]
