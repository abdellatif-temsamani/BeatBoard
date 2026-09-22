"""Pure Spotify OAuth HTTP helpers.

Leaf module – no dependency on tokens/flow/callback. Used by tokens and flow.
"""

from __future__ import annotations

import secrets
import time
import urllib.parse

import requests

from ..logs import log
from .constants import DEFAULT_SCOPES, SPOTIFY_AUTH_URL, SPOTIFY_TOKEN_URL


def build_auth_url(
    client_id: str,
    redirect_uri: str,
    scope: str = DEFAULT_SCOPES,
    state: str | None = None,
) -> str:
    """Build Spotify Authorization Code URL."""
    if state is None:
        state = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "show_dialog": "false",
    }
    return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}", state  # type: ignore[return-value]


def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for access/refresh tokens."""
    t0 = time.perf_counter()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    dt = (time.perf_counter() - t0) * 1000
    if not resp.ok:
        log(
            "api",
            f"[red]api[/red] [dim]·[/dim] token exchange [red]{resp.status_code}[/red] [dim]·[/dim] [red]{dt:.0f}ms[/red]",
        )
        raise RuntimeError(
            f"Spotify token exchange failed {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    log(
        "api",
        f"[green]api[/green] [dim]·[/dim] token exchange [green]{resp.status_code}[/green] [dim]·[/dim] [green]{dt:.0f}ms[/green] [dim](expires {data.get('expires_in')}s)[/dim]",
    )
    return data


def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Refresh an access token using a refresh token."""
    t0 = time.perf_counter()
    resp = requests.post(
        SPOTIFY_TOKEN_URL,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=10,
    )
    dt = (time.perf_counter() - t0) * 1000
    if not resp.ok:
        log(
            "api",
            f"[red]api[/red] [dim]·[/dim] refresh [red]{resp.status_code}[/red] [dim]·[/dim] [red]{dt:.0f}ms[/red]",
        )
        raise RuntimeError(
            f"Spotify refresh failed {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    log(
        "api",
        f"[green]api[/green] [dim]·[/dim] refresh [green]{resp.status_code}[/green] [dim]·[/dim] [green]{dt:.0f}ms[/green] [dim](expires {data.get('expires_in')}s)[/dim]",
    )
    return data
