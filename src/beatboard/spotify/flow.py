"""OAuth flow orchestration – browser + callback + token ensemble.

Top layer: imports from tokens, oauth and callback. No module should import from
flow except the facade, to avoid cycles.
"""

from __future__ import annotations

import time
import urllib.parse
import webbrowser
from pathlib import Path

from rich import print

from ..globs import Globs
from ..logs import log
from .callback import _run_local_server
from .constants import (
    DEFAULT_CLIENT_ID,
    DEFAULT_CLIENT_SECRET,
    DEFAULT_REDIRECT_URI,
    DEFAULT_SCOPES,
)
from .oauth import build_auth_url, exchange_code_for_token
from .tokens import _try_refresh_token, get_spotify_token, save_spotify_tokens


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
    client_id = client_id or getattr(globs, "spotify_client_id", None) or DEFAULT_CLIENT_ID
    client_secret = (
        client_secret or getattr(globs, "spotify_client_secret", None) or DEFAULT_CLIENT_SECRET
    )
    redirect_uri = (
        redirect_uri or getattr(globs, "spotify_redirect_uri", None) or DEFAULT_REDIRECT_URI
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
    client_id = getattr(globs, "spotify_client_id", None)
    client_secret = getattr(globs, "spotify_client_secret", None)
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
        "Add [cyan]spotify_token[/cyan] to [dim]~/.config/beatboard/config.yaml[/dim]. "
        "Alternatively, ensure [cyan]spotify_client_id[/cyan] and "
        "[cyan]spotify_client_secret[/cyan] are set in config and run with [cyan]--api[/cyan] "
        "to start browser authentication at http://127.0.0.1:8888/callback. "
        "Obtain credentials from https://developer.spotify.com/dashboard"
    )
    return False
