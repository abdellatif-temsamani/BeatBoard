"""Spotify authentication & token management.

Handles token resolution, OAuth Authorization Code flow, refresh, persistence
and availability checks.
"""

from __future__ import annotations

import os
import secrets
import time
import urllib.parse
import webbrowser
from pathlib import Path

import requests
import yaml
from rich import print

from ..globs import Globs
from ..logs import log
from .callback import _run_local_server
from .constants import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPES,
    SPOTIFY_AUTH_URL,
    SPOTIFY_TOKEN_URL,
)


def _get_session():  # lazy to avoid circular at import time
    from .session import _get_session as _gs

    return _gs()


def get_spotify_token() -> str | None:
    """Resolve a Spotify API token from env or config file."""
    for env_var in ("SPOTIFY_TOKEN", "SPOTIFY_ACCESS_TOKEN", "BEATBOARD_SPOTIFY_TOKEN"):
        token = os.getenv(env_var)
        if token:
            token = token.strip()
            if token:
                log(
                    "api",
                    f"[cyan]api[/cyan] [dim]·[/dim] token from env:[green]{env_var}[/green]",
                )
                return token

    globs = Globs()
    for attr in ("spotify_token", "spotify_access_token"):
        token = getattr(globs, attr, None)
        if isinstance(token, str) and token.strip():
            token = token.strip()
            return token

    log("api", "[yellow]api[/yellow] [dim]·[/dim] no token found")
    return None


def _try_client_credentials_token() -> str | None:
    """Attempt to obtain a token via Spotify Client Credentials flow."""
    globs = Globs()
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or getattr(
        globs, "spotify_client_id", None
    )
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or getattr(
        globs, "spotify_client_secret", None
    )

    if not client_id or not client_secret:
        return None

    try:
        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={"grant_type": "client_credentials"},
            auth=(client_id, client_secret),
            timeout=5,
        )
        if resp.ok:
            data = resp.json()
            token = data.get("access_token")
            if isinstance(token, str) and token.strip():
                return token.strip()
    except requests.RequestException:
        return None
    return None


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


def save_spotify_tokens(
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    config_path: Path | None = None,
) -> None:
    """Persist Spotify tokens to the config file and Globs."""
    globs = Globs()
    if config_path is None:
        config_path = getattr(globs, "config_path", None)
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
            data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                data = {}
        else:
            data = {}
        data["spotify_token"] = access_token
        if refresh_token is not None:
            data["spotify_refresh_token"] = refresh_token
        if "spotify_client_id" not in data or not data["spotify_client_id"]:
            data["spotify_client_id"] = getattr(
                globs, "spotify_client_id", DEFAULT_CLIENT_ID
            )
        if "spotify_client_secret" not in data or not data["spotify_client_secret"]:
            data["spotify_client_secret"] = getattr(
                globs, "spotify_client_secret", DEFAULT_CLIENT_SECRET
            )
        if "spotify_redirect_uri" not in data or not data["spotify_redirect_uri"]:
            data["spotify_redirect_uri"] = getattr(
                globs, "spotify_redirect_uri", DEFAULT_REDIRECT_URI
            )
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")
        dt = (time.perf_counter() - t0) * 1000
        log(
            "api",
            f"[green]api[/green] [dim]·[/dim] token saved [dim]·[/dim] [green]{dt:.0f}ms[/green]",
        )
    except OSError as exc:
        print(
            f"[yellow]Warning:[/yellow] could not save Spotify token to {config_path}: {exc}"
        )


def run_oauth_flow(
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    scope: str = DEFAULT_SCOPES,
    config_path: Path | None = None,
    open_browser: bool = True,
    timeout: int = 180,
) -> str | None:
    """Run the full Spotify Authorization Code flow."""
    globs = Globs()
    client_id = (
        client_id
        or os.getenv("SPOTIFY_CLIENT_ID")
        or getattr(globs, "spotify_client_id", None)
        or DEFAULT_CLIENT_ID
    )
    client_secret = (
        client_secret
        or os.getenv("SPOTIFY_CLIENT_SECRET")
        or getattr(globs, "spotify_client_secret", None)
        or DEFAULT_CLIENT_SECRET
    )
    redirect_uri = (
        redirect_uri
        or os.getenv("SPOTIFY_REDIRECT_URI")
        or getattr(globs, "spotify_redirect_uri", None)
        or DEFAULT_REDIRECT_URI
    )

    if not client_id:
        print("[red bold]Error:[/red bold] Spotify client_id not configured.")
        return None
    if not client_secret:
        print("[red bold]Error:[/red bold] Spotify client_secret not configured.")
        return None

    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8888

    oauth_t0 = time.perf_counter()
    log(
        "api",
        f"[cyan]api[/cyan] [dim]·[/dim] oauth start [dim]·[/dim] [cyan]{redirect_uri}[/cyan]",
    )

    auth_url, state = build_auth_url(client_id, redirect_uri, scope)  # type: ignore[misc]
    if isinstance(auth_url, tuple):
        auth_url, state = auth_url  # type: ignore[misc]

    print("[bold blue]Spotify authentication required[/bold blue]")
    print(f"Opening browser to: [cyan]{auth_url}[/cyan]")
    print(f"Waiting for callback on [dim]{redirect_uri}[/dim] (timeout {timeout}s)…")
    print("If the browser does not open, manually visit the URL above.")

    if open_browser:
        try:
            webbrowser.open(auth_url)
        except Exception:
            pass

    code, returned_state, error = _run_local_server(host, port, timeout)
    dt_cb = (time.perf_counter() - oauth_t0) * 1000
    if error and error != "timeout":
        log(
            "api",
            f"[red]api[/red] [dim]·[/dim] oauth callback error [dim]·[/dim] [red]{dt_cb:.0f}ms[/red] [dim]({error})[/dim]",
        )

    if error == "timeout":
        print("[red bold]Error:[/red bold] Authentication timed out. Please try again.")
        return None
    if error:
        print(f"[red bold]Error:[/red bold] Spotify auth error: {error}")
        return None
    if not code:
        print("[red bold]Error:[/red bold] No authorization code received.")
        return None
    if returned_state != state:
        print("[yellow]Warning:[/yellow] State mismatch – continuing anyway.")

    try:
        token_data = exchange_code_for_token(
            code, client_id, client_secret, redirect_uri
        )
    except RuntimeError as exc:
        print(f"[red bold]Error:[/red bold] {exc}")
        return None

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    expires_in = token_data.get("expires_in")

    if not access_token:
        print("[red bold]Error:[/red bold] No access token in response.")
        return None

    save_spotify_tokens(
        access_token, refresh_token, expires_in, config_path=config_path
    )
    dt_total = (time.perf_counter() - oauth_t0) * 1000
    log(
        "api",
        f"[green]api[/green] [dim]·[/dim] oauth done [dim]·[/dim] [green]{dt_total:.0f}ms[/green] [dim](expires {expires_in}s)[/dim]",
    )
    print(
        "[green bold]Spotify authentication successful![/green bold] Token saved to config."
    )
    return access_token


def _try_refresh_token(config_path: Path | None = None) -> str | None:
    """Attempt to refresh the access token using the stored refresh token."""
    t0 = time.perf_counter()
    globs = Globs()
    refresh_token = getattr(globs, "spotify_refresh_token", None) or os.getenv(
        "SPOTIFY_REFRESH_TOKEN"
    )
    if not refresh_token:
        log("api", "[yellow]api[/yellow] [dim]·[/dim] no refresh token")
        return None
    log("api", "[cyan]api[/cyan] [dim]·[/dim] [yellow]refreshing token…[/yellow]")
    client_id = (
        os.getenv("SPOTIFY_CLIENT_ID")
        or getattr(globs, "spotify_client_id", None)
        or DEFAULT_CLIENT_ID
    )
    client_secret = (
        os.getenv("SPOTIFY_CLIENT_SECRET")
        or getattr(globs, "spotify_client_secret", None)
        or DEFAULT_CLIENT_SECRET
    )
    try:
        data = refresh_access_token(refresh_token, client_id, client_secret)
        new_token = data.get("access_token")
        new_refresh = data.get("refresh_token") or refresh_token
        expires_in = data.get("expires_in")
        if new_token:
            save_spotify_tokens(
                new_token, new_refresh, expires_in, config_path=config_path
            )
            dt = (time.perf_counter() - t0) * 1000
            log(
                "api",
                f"[green]api[/green] [dim]·[/dim] refresh ok [dim]·[/dim] [green]{dt:.0f}ms[/green]",
            )
            return new_token
    except RuntimeError as exc:
        dt = (time.perf_counter() - t0) * 1000
        log(
            "api",
            f"[red]api[/red] [dim]·[/dim] refresh failed [dim]·[/dim] [red]{dt:.0f}ms[/red]",
        )
        print(f"[yellow]Warning:[/yellow] Token refresh failed: {exc}")
    return None


def ensure_valid_token(
    config_path: Path | None = None, force_refresh: bool = False
) -> str | None:
    """Ensure a valid access token is available, refreshing or authenticating if needed."""
    t0 = time.perf_counter()
    if not force_refresh:
        token = get_spotify_token()
        if token:
            return token

    refreshed = _try_refresh_token(config_path=config_path)
    if refreshed:
        return refreshed
    if force_refresh:
        dt = (time.perf_counter() - t0) * 1000
        log(
            "api",
            f"[yellow]api[/yellow] [dim]·[/dim] force refresh failed [dim]·[/dim] [yellow]{dt:.0f}ms[/yellow]",
        )

    log("api", "[yellow]api[/yellow] [dim]·[/dim] no token, starting oauth…")
    return run_oauth_flow(config_path=config_path)


def check_spotify_api_available() -> bool:
    """Check whether Spotify API can be used (token present or OAuth possible)."""
    t0 = time.perf_counter()
    token = get_spotify_token()
    if token:
        dt = (time.perf_counter() - t0) * 1000
        log(
            "api",
            f"[green]api[/green] [dim]·[/dim] token ok [dim]·[/dim] [green]{dt:.0f}ms[/green]",
        )
        return True

    globs = Globs()
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or getattr(
        globs, "spotify_client_id", None
    )
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or getattr(
        globs, "spotify_client_secret", None
    )
    has_oauth = bool(client_id and client_secret)
    dt = (time.perf_counter() - t0) * 1000
    log(
        "api",
        f"[yellow]api[/yellow] [dim]·[/dim] no token [dim]·[/dim] oauth={'[green]yes[/green]' if has_oauth else '[red]no[/red]'} [dim]·[/dim] [cyan]{dt:.0f}ms[/cyan]",
    )
    if has_oauth:
        return True

    print(
        "[red bold]Error:[/red bold] Spotify API token not found. "
        "Set [cyan]SPOTIFY_TOKEN[/cyan] environment variable or add "
        "[cyan]spotify_token[/cyan] to [dim]~/.config/beatboard/config.yaml[/dim]. "
        "Alternatively, ensure [cyan]spotify_client_id[/cyan] and "
        "[cyan]spotify_client_secret[/cyan] are set and run with [cyan]--api[/cyan] "
        "to start browser authentication at http://127.0.0.1:8888/callback. "
        "Obtain credentials from https://developer.spotify.com/dashboard"
    )
    return False
