"""Spotify authentication & token management – facade.

Keeps the flat ``beatboard.spotify.auth`` import path stable while
implementation lives in submodules:

* ``oauth.py``  – pure Spotify OAuth HTTP (build_auth_url, exchange, refresh)
* ``tokens.py`` – token lifecycle (get, save, client-credentials, refresh attempt)
* ``flow.py``   – orchestration (run_oauth_flow, ensure_valid_token, check)

Layering: constants (leaf) → session/callback (leaf) → oauth (leaf HTTP)
→ tokens (uses oauth) → flow (uses tokens+oauth+callback).  This facade
re-exports everything so both ``from beatboard.spotify import X`` and
``from beatboard.spotify.auth import X`` keep working.
"""

from __future__ import annotations

from .flow import (
    check_spotify_api_available,
    ensure_valid_token,
    run_oauth_flow,
)
from .oauth import build_auth_url, exchange_code_for_token, refresh_access_token
from .tokens import (
    _get_session,
    _try_client_credentials_token,
    _try_refresh_token,
    get_spotify_token,
    save_spotify_tokens,
)

__all__ = [
    "get_spotify_token",
    "_try_client_credentials_token",
    "build_auth_url",
    "exchange_code_for_token",
    "refresh_access_token",
    "save_spotify_tokens",
    "run_oauth_flow",
    "_try_refresh_token",
    "ensure_valid_token",
    "check_spotify_api_available",
    "_get_session",
]
