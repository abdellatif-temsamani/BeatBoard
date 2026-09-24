"""Token lifecycle – resolution, persistence and refresh.

Layer: constants → oauth → tokens. No dependency on flow/callback.
"""

from __future__ import annotations

import time
from pathlib import Path

import requests
import yaml
from rich import print

from ..globs import Globs
from ..logs import log
from .constants import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_REDIRECT_URI,
    SPOTIFY_TOKEN_URL,
)
from .oauth import refresh_access_token


def _get_session():  # lazy to avoid circular at import time
    from .session import _get_session as _gs

    return _gs()


def get_spotify_token() -> str | None:
    """Resolve a Spotify API token from config."""
    globs = Globs()
    for attr in ('spotify_token', 'spotify_access_token'):
        token = getattr(globs, attr, None)
        if isinstance(token, str) and token.strip():
            token = token.strip()
            return token

    log('api', '[yellow]api[/yellow] [dim]·[/dim] no token found')
    return None


def _try_client_credentials_token() -> str | None:
    """Attempt to obtain a token via Spotify Client Credentials flow."""
    globs = Globs()
    client_id = getattr(globs, 'spotify_client_id', None)
    client_secret = getattr(globs, 'spotify_client_secret', None)

    if not client_id or not client_secret:
        return None

    try:
        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={'grant_type': 'client_credentials'},
            auth=(client_id, client_secret),
            timeout=5,
        )
        if resp.ok:
            data = resp.json()
            token = data.get('access_token')
            if isinstance(token, str) and token.strip():
                return token.strip()
    except requests.RequestException:
        return None
    return None


def save_spotify_tokens(
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    config_path: Path | None = None,
) -> None:
    """Persist Spotify tokens to the config file and Globs."""
    globs = Globs()
    if config_path is None:
        config_path = getattr(globs, 'config_path', None)
        if config_path is None:
            from ..config import get_config_path

            config_path = get_config_path()
        config_path = Path(config_path)

    globs.spotify_token = access_token
    if refresh_token is not None:
        globs.spotify_refresh_token = refresh_token
    t0 = time.perf_counter()

    try:
        if config_path.is_file():
            data = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
        data['spotify_token'] = access_token
        if refresh_token is not None:
            data['spotify_refresh_token'] = refresh_token
        if 'spotify_client_id' not in data or not data['spotify_client_id']:
            data['spotify_client_id'] = getattr(
                globs, 'spotify_client_id', DEFAULT_CLIENT_ID
            )
        if 'spotify_client_secret' not in data or not data['spotify_client_secret']:
            data['spotify_client_secret'] = getattr(
                globs, 'spotify_client_secret', DEFAULT_CLIENT_SECRET
            )
        if 'spotify_redirect_uri' not in data or not data['spotify_redirect_uri']:
            data['spotify_redirect_uri'] = getattr(
                globs, 'spotify_redirect_uri', DEFAULT_REDIRECT_URI
            )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(data, sort_keys=True), encoding='utf-8')
        dt = (time.perf_counter() - t0) * 1000
        log(
            'api',
            f'[green]api[/green] [dim]·[/dim] token saved [dim]·[/dim] [green]{dt:.0f}ms[/green]',
        )
    except OSError as exc:
        print(
            f'[yellow]Warning:[/yellow] could not save Spotify token to {config_path}: {exc}'
        )


def _try_refresh_token(config_path: Path | None = None) -> str | None:
    """Attempt to refresh the access token using the stored refresh token."""
    t0 = time.perf_counter()
    globs = Globs()
    refresh_token = getattr(globs, 'spotify_refresh_token', None)
    if not refresh_token:
        log('api', '[yellow]api[/yellow] [dim]·[/dim] no refresh token')
        return None
    log('api', '[cyan]api[/cyan] [dim]·[/dim] [yellow]refreshing token…[/yellow]')
    client_id = getattr(globs, 'spotify_client_id', None) or DEFAULT_CLIENT_ID
    client_secret = (
        getattr(globs, 'spotify_client_secret', None) or DEFAULT_CLIENT_SECRET
    )
    try:
        data = refresh_access_token(refresh_token, client_id, client_secret)
        new_token = data.get('access_token')
        new_refresh = data.get('refresh_token') or refresh_token
        expires_in = data.get('expires_in')
        if new_token:
            save_spotify_tokens(
                new_token, new_refresh, expires_in, config_path=config_path
            )
            dt = (time.perf_counter() - t0) * 1000
            log(
                'api',
                f'[green]api[/green] [dim]·[/dim] refresh ok [dim]·[/dim] [green]{dt:.0f}ms[/green]',
            )
            return new_token
    except RuntimeError as exc:
        dt = (time.perf_counter() - t0) * 1000
        log(
            'api',
            f'[red]api[/red] [dim]·[/dim] refresh failed [dim]·[/dim] [red]{dt:.0f}ms[/red]',
        )
        print(f'[yellow]Warning:[/yellow] Token refresh failed: {exc}')
    return None
