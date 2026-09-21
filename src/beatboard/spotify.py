"""Spotify WebSocket integration for BeatBoard.

This module provides an alternative to ``playerctl`` for platforms where
``playerctl`` is unavailable. When the ``--api`` (alias ``--spotify``) flag
is used, BeatBoard authenticates with the user's Spotify account and uses
a Spotify WebSocket (Dealer) connection for real-time track change
notifications – pure push, no REST polling.

Authentication:
    The access token is resolved in the following priority order:
    1. Environment variables: SPOTIFY_TOKEN, SPOTIFY_ACCESS_TOKEN,
       BEATBOARD_SPOTIFY_TOKEN
    2. Config file: ``spotify_token`` from ``~/.config/beatboard/config.yaml``
        (stored in Globs via :mod:`beatboard.config`)
    3. OAuth Authorization Code flow (using ``spotify_client_id``,
       ``spotify_client_secret`` and ``spotify_redirect_uri`` from config).
         Tokens are persisted back to the config file (``spotify_token`` and
         ``spotify_refresh_token``).
    4. Spotify OAuth client-credentials helper (if client id/secret are set).

Real-time transport:
    Spotify Dealer WebSocket
        ``wss://dealer.spotify.com/?access_token={token}``
    The Dealer pushes cluster / player_state updates instantly when the
    track changes. A lightweight heartbeat is maintained and the connection
    auto-reconnects with exponential backoff. No REST polling fallback.

Requires scope ``user-read-currently-playing`` or
``user-read-playback-state``.
"""

from __future__ import annotations

import asyncio
import base64
import html as html_lib
import http.server
import json
import os
import queue
import re
import secrets
import socketserver
import threading
import time
import urllib.parse
import webbrowser
from pathlib import Path
from typing import Tuple

import requests
import yaml
from rich import print

from .globs import Globs
from .logs import log

SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
DEFAULT_SCOPES = "user-read-currently-playing user-read-playback-state"
DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"
SPOTIFY_DEALER_WS_URL = "wss://dealer.spotify.com/?access_token={token}"
SPOTIFY_CURRENTLY_PLAYING_URL = "https://api.spotify.com/v1/me/player/currently-playing"
# No hardcoded credentials – must be provided via config.yaml (spotify_client_id/secret)
# or env SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET
DEFAULT_CLIENT_ID = ""
DEFAULT_CLIENT_SECRET = ""


def get_spotify_token() -> str | None:
    """Resolve a Spotify API token from env or config file.

    Priority:
        1. Environment variables
        2. Config file (``spotify_token`` in ``config.yaml``, exposed via Globs)

    Note:
        Client-credentials flow is intentionally NOT used here. Tokens
        obtained via client credentials lack a user context and cannot
        access ``/v1/me/player/currently-playing`` (Spotify returns
        ``404 Invalid username`` for such tokens). User authentication
        must go through :func:`ensure_valid_token` / OAuth Authorization
        Code flow.

    Returns:
        The bearer token string if found, otherwise None.
    """
    # 1. Environment variables (highest priority)
    for env_var in ("SPOTIFY_TOKEN", "SPOTIFY_ACCESS_TOKEN", "BEATBOARD_SPOTIFY_TOKEN"):
        token = os.getenv(env_var)
        if token:
            token = token.strip()
            if token:
                log("api", f"[dim][api][/dim] token source=env:{env_var}")
                return token

    # 2. Config file via Globs (populated from ~/.config/beatboard/config.yaml)
    globs = Globs()
    for attr in ("spotify_token", "spotify_access_token"):
        token = getattr(globs, attr, None)
        if isinstance(token, str) and token.strip():
            token = token.strip()
            return token

    log("api", "[dim][api][/dim] no token in env/config")
    return None


def _try_client_credentials_token() -> str | None:
    """Attempt to obtain a token via Spotify Client Credentials flow.

    Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET env vars or
    config values. Returns None if credentials are missing or the request fails.

    Note: Client credentials tokens cannot access user playback endpoints,
    but this provides a fallback for testing and non-user scopes.
    """
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
    return f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}", state


def exchange_code_for_token(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """Exchange authorization code for access/refresh tokens."""
    t0 = time.perf_counter()
    log("api", "[dim][api][/dim] POST token exchange grant=authorization_code")
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
    log(
        "api",
        f"[dim][api][/dim] token exchange status={resp.status_code} took={dt:.0f}ms",
    )
    if not resp.ok:
        raise RuntimeError(
            f"Spotify token exchange failed {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    log(
        "api",
        f"[dim][api][/dim] token exchange ok expires_in={data.get('expires_in')} took={dt:.0f}ms",
    )
    return data


def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """Refresh an access token using a refresh token."""
    t0 = time.perf_counter()
    log("api", "[dim][api][/dim] POST token refresh grant=refresh_token")
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
    log("api", f"[dim][api][/dim] refresh status={resp.status_code} took={dt:.0f}ms")
    if not resp.ok:
        raise RuntimeError(
            f"Spotify refresh failed {resp.status_code}: {resp.text[:500]}"
        )
    data = resp.json()
    log(
        "api",
        f"[dim][api][/dim] refresh ok expires_in={data.get('expires_in')} took={dt:.0f}ms",
    )
    return data


def save_spotify_tokens(
    access_token: str,
    refresh_token: str | None = None,
    expires_in: int | None = None,
    config_path: Path | None = None,
) -> None:
    """Persist Spotify tokens to the config file and Globs.

    Args:
        access_token: New access token.
        refresh_token: New refresh token (if provided, otherwise keeps existing).
        expires_in: Expires in seconds (currently unused except for future expiry handling).
        config_path: Path to config.yaml. If None, uses Globs.config_path or default.
    """
    globs = Globs()
    if config_path is None:
        config_path = getattr(globs, "config_path", None)
        if config_path is None:
            from .config import get_config_path

            config_path = get_config_path()
        config_path = Path(config_path)

    # Update Globs in-memory
    globs.spotify_token = access_token
    if refresh_token is not None:
        globs.spotify_refresh_token = refresh_token
    t0 = time.perf_counter()
    log(
        "api",
        f"[dim][api][/dim] save tokens to {config_path} refresh={'yes' if refresh_token else 'no'}",
    )

    # Update file on disk – preserve other keys
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
        # Ensure client defaults are present if missing (helps first-time setup)
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
            f"[dim][api][/dim] config write done took={dt:.0f}ms path={config_path}",
        )
    except OSError as exc:
        print(
            f"[yellow]Warning:[/yellow] could not save Spotify token to {config_path}: {exc}"
        )


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP handler that captures Spotify OAuth callback."""

    # Shared BeatBoard callback styling – keeps browser tab polished instead of bare <h1>
    _STYLE = """
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;background:radial-gradient(900px 500px at 50% -10%, #1e2a4a 0%, #0a0a12 55%, #050508 100%);color:#e8e8ef;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Inter,Helvetica,Arial,sans-serif;padding:24px}
.card{width:100%;max-width:480px;background:rgba(24,24,33,.92);backdrop-filter:blur(12px);border:1px solid rgba(255,255,255,.08);border-radius:24px;padding:40px 32px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.6),0 1px 0 rgba(255,255,255,.06) inset}
.logo{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#6b7cff;font-weight:700;margin-bottom:22px}
.icon{width:72px;height:72px;border-radius:50%;display:flex;align-items:center;justify-content:center;margin:0 auto 20px;font-size:34px}
.icon.success{background:linear-gradient(135deg,#1DB954,#1ed760);color:#fff;box-shadow:0 8px 24px rgba(29,185,84,.4)}
.icon.error{background:linear-gradient(135deg,#ff4d6d,#ff3b30);color:#fff;box-shadow:0 8px 24px rgba(255,59,48,.35)}
.icon.warn{background:linear-gradient(135deg,#ffb020,#ff8c00);color:#fff;box-shadow:0 8px 24px rgba(255,176,32,.3)}
h1{font-size:24px;font-weight:700;margin:0 0 10px;letter-spacing:-.02em}
p{color:#a8a8b8;line-height:1.6;margin:0 0 16px;font-size:15px}
.hint{font-size:13px;color:#7a7a8a}
.btn{margin-top:18px;appearance:none;border:0;background:#fff;color:#0a0a12;font-weight:600;padding:10px 22px;border-radius:999px;cursor:pointer;font-size:14px}
.btn:hover{background:#f0f0f0}
.btn-secondary{background:rgba(255,255,255,.08);color:#e8e8ef;border:1px solid rgba(255,255,255,.12)}
.btn-secondary:hover{background:rgba(255,255,255,.14)}
.footer{margin-top:26px;font-size:11px;color:#5a5a6a;letter-spacing:.04em}
code{background:rgba(255,255,255,.08);padding:2px 6px;border-radius:6px;font-size:12px;color:#e8e8ef;word-break:break-all}
"""

    def _html(self, *, icon: str, title: str, body: str, footer: str = "") -> bytes:
        doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>BeatBoard — {html_lib.escape(title)}</title>
<style>{self._STYLE}</style>
</head>
<body>
  <div class="card">
    <div class="logo">♫ BeatBoard</div>
    <div class="icon {icon}">{'✓' if icon=='success' else '✕' if icon=='error' else '!'}</div>
    <h1>{html_lib.escape(title)}</h1>
    {body}
    {footer}
  </div>
</body>
</html>"""
        return doc.encode()

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        # Expected: /callback?code=...&state=...
        if parsed.path.endswith("/callback"):
            code = qs.get("code", [None])[0]
            state = qs.get("state", [None])[0]
            error = qs.get("error", [None])[0]
            self.server.auth_code = code  # type: ignore[attr-defined]
            self.server.auth_state = state  # type: ignore[attr-defined]
            self.server.auth_error = error  # type: ignore[attr-defined]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if error:
                safe = html_lib.escape(error)
                body = f'<p>Spotify returned an error and BeatBoard could not connect.</p><p><code>{safe}</code></p><p class="hint">Close this window and run <code>beatboard --api</code> again to retry. Check your app redirect URI is <code>http://127.0.0.1:8888/callback</code>.</p><button class="btn btn-secondary" onclick="window.close()">Close window</button>'
                self.wfile.write(
                    self._html(
                        icon="error",
                        title="Authentication failed",
                        body=body,
                        footer='<div class="footer">Need help? See Spotify Dashboard → Edit Settings</div>',
                    )
                )
            elif code:
                body = """<p>Your Spotify account is now connected. BeatBoard will stream track changes via WebSocket — no polling.</p><p class="hint">You can close this window and return to the terminal. It will try to close automatically in <span id="cd">4</span>s.</p><button class="btn" onclick="window.close()">Close window</button><script>let n=4,el=document.getElementById('cd');const t=setInterval(()=>{n--;if(el)el.textContent=n;if(n<=0){clearInterval(t);try{window.close()}catch(e){}}},1000)</script>"""
                self.wfile.write(
                    self._html(
                        icon="success",
                        title="Authentication successful!",
                        body=body,
                        footer='<div class="footer">Listening via wss://dealer.spotify.com • BeatBoard</div>',
                    )
                )
            else:
                body = '<p>No authorization code was received. The redirect may have been blocked.</p><p class="hint">Close this window and run <code>beatboard --api</code> again. Allow the browser to open <code>http://127.0.0.1:8888/callback</code>.</p><button class="btn btn-secondary" onclick="window.close()">Close window</button>'
                self.wfile.write(
                    self._html(
                        icon="warn",
                        title="No code received",
                        body=body,
                    )
                )
            # Signal completion
            try:
                self.server.code_queue.put((code, state, error), block=False)  # type: ignore[attr-defined]
            except queue.Full:
                pass
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(
                self._html(
                    icon="error",
                    title="Not found",
                    body='<p class="hint">Unknown path. Expected <code>/callback?code=...</code></p>',
                )
            )

    def log_message(self, format, *args):  # noqa: A002
        # Suppress default logging
        return


def _run_local_server(
    host: str = "127.0.0.1", port: int = 8888, timeout: int = 180
) -> tuple[str | None, str | None, str | None]:
    """Run a temporary HTTP server to capture OAuth callback."""
    code_queue: queue.Queue = queue.Queue()
    t0 = time.perf_counter()
    log(
        "api",
        f"[dim][api][/dim] callback server start http://{host}:{port}/callback timeout={timeout}s",
    )

    # Allow address reuse
    class ReusableTCPServer(socketserver.TCPServer):
        allow_reuse_address = True

    with ReusableTCPServer((host, port), _CallbackHandler) as httpd:
        httpd.code_queue = code_queue  # type: ignore[attr-defined]
        httpd.auth_code = None  # type: ignore[attr-defined]
        httpd.auth_state = None  # type: ignore[attr-defined]
        httpd.auth_error = None  # type: ignore[attr-defined]
        # Run in a thread so we can timeout
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            code, state, error = code_queue.get(timeout=timeout)
            dt = (time.perf_counter() - t0) * 1000
            log(
                "api",
                f"[dim][api][/dim] callback received ok={bool(code)} error={error} wait={dt:.0f}ms",
            )
            return code, state, error
        except queue.Empty:
            dt = (time.perf_counter() - t0) * 1000
            log("api", f"[dim][api][/dim] callback timeout wait={dt:.0f}ms")
            return None, None, "timeout"
        finally:
            httpd.shutdown()
            thread.join(timeout=2)
            dt = (time.perf_counter() - t0) * 1000
            log("api", f"[dim][api][/dim] callback server stopped total={dt:.0f}ms")


def run_oauth_flow(
    client_id: str | None = None,
    client_secret: str | None = None,
    redirect_uri: str | None = None,
    scope: str = DEFAULT_SCOPES,
    config_path: Path | None = None,
    open_browser: bool = True,
    timeout: int = 180,
) -> str | None:
    """Run the full Spotify Authorization Code flow.

    Opens the user's browser to Spotify's authorize endpoint, starts a local
    HTTP server to receive the callback, exchanges the code for tokens and
    persists them to the config file.

    Returns:
        The access token if successful, None otherwise.
    """
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

    # Parse redirect_uri to get host/port
    parsed = urllib.parse.urlparse(redirect_uri)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8888

    oauth_t0 = time.perf_counter()
    log(
        "api",
        f"[dim][api][/dim] oauth flow start redirect={redirect_uri} scope={scope}",
    )

    auth_url, state = build_auth_url(client_id, redirect_uri, scope)
    # State is returned as tuple (url, state) by our helper; handle both signatures
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
    log(
        "api", f"[dim][api][/dim] oauth callback phase took={dt_cb:.0f}ms error={error}"
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
        f"[dim][api][/dim] oauth flow done took={dt_total:.0f}ms expires_in={expires_in}",
    )
    print(
        "[green bold]Spotify authentication successful![/green bold] Token saved to config."
    )
    return access_token


def ensure_valid_token(config_path: Path | None = None) -> str | None:
    """Ensure a valid access token is available, refreshing or authenticating if needed.

    Returns:
        A valid access token or None if authentication fails.
    """
    t0 = time.perf_counter()
    token = get_spotify_token()
    if token:
        log(
            "api",
            f"[dim][api][/dim] ensure_valid_token hit existing took={(time.perf_counter() - t0) * 1000:.0f}ms",
        )
        # Quick validation: try a cheap request? We just return it; 401 handling will refresh.
        return token

    globs = Globs()
    # Try refresh token if we have one
    refresh_token = getattr(globs, "spotify_refresh_token", None) or os.getenv(
        "SPOTIFY_REFRESH_TOKEN"
    )
    if refresh_token:
        log("api", "[dim][api][/dim] ensure_valid_token trying refresh")
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
                log(
                    "api",
                    f"[dim][api][/dim] ensure_valid_token refresh ok took={(time.perf_counter() - t0) * 1000:.0f}ms",
                )
                return new_token
        except RuntimeError as exc:
            log(
                "api",
                f"[dim][api][/dim] ensure_valid_token refresh failed took={(time.perf_counter() - t0) * 1000:.0f}ms",
            )
            print(f"[yellow]Warning:[/yellow] Token refresh failed: {exc}")

    # Fall back to full OAuth flow
    log(
        "api",
        f"[dim][api][/dim] ensure_valid_token falling back to oauth took={(time.perf_counter() - t0) * 1000:.0f}ms",
    )
    return run_oauth_flow(config_path=config_path)


def check_spotify_api_available() -> bool:
    """Check whether Spotify API can be used (token present or OAuth possible).

    If no token is present but client credentials are configured, this returns
    ``True`` so :func:`watch_spotify_api` can run the OAuth Authorization
    Code flow with the local callback at ``http://127.0.0.1:8888/callback``.
    For non-interactive tests, callers can mock ``get_spotify_token`` or
    ``run_oauth_flow``.

    Returns:
        True if a token can be resolved or OAuth is possible, False otherwise.
    """
    t0 = time.perf_counter()
    token = get_spotify_token()
    if token:
        log(
            "api",
            f"[dim][api][/dim] check available token=yes took={(time.perf_counter() - t0) * 1000:.0f}ms",
        )
        return True

    # No token – see if OAuth is possible (needs both id and secret)
    globs = Globs()
    client_id = os.getenv("SPOTIFY_CLIENT_ID") or getattr(
        globs, "spotify_client_id", None
    )
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET") or getattr(
        globs, "spotify_client_secret", None
    )
    has_oauth = bool(client_id and client_secret)
    log(
        "api",
        f"[dim][api][/dim] check available token=no oauth={has_oauth} took={(time.perf_counter() - t0) * 1000:.0f}ms",
    )
    if has_oauth:
        # Token missing but we can authenticate via browser flow.
        # Let watch_spotify_api handle run_oauth_flow / ensure_valid_token.
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


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------


def _build_websocket_url(token: str) -> str:
    """Build the Spotify WebSocket (Dealer) URL.

    Priority:
      1. ``spotify_websocket_url`` from Globs / config / env
         (supports ``{token}`` placeholder).
      2. Default Dealer URL ``wss://dealer.spotify.com/?access_token={token}``.

    Returns:
        A ``wss://`` URL ready for ``websockets.connect``.
    """
    globs = Globs()
    custom = getattr(globs, "spotify_websocket_url", None) or os.getenv(
        "SPOTIFY_WEBSOCKET_URL"
    )
    if custom:
        custom = custom.strip()
        if custom:
            if "{token}" in custom:
                return custom.format(token=token)
            # If custom URL has no placeholder, append token as query param
            if "access_token" not in custom:
                sep = "&" if "?" in custom else "?"
                return f"{custom}{sep}access_token={urllib.parse.quote(token, safe='')}"
            return custom
    return SPOTIFY_DEALER_WS_URL.format(token=urllib.parse.quote(token, safe=""))


def _extract_track_from_payload(
    data: object,
) -> Tuple[str | None, str | None, str | None] | None:
    """Extract (art_url, title, artist) from a WebSocket message payload.

    Handles several shapes:
      * Spotify REST ``currently-playing`` object (``{item: {...}}``)
      * Dealer ``cluster`` / ``player_state`` nesting
      * Generic ``payloads`` list wrapping the above
      * Simple ``{art_url, title, artist}`` push messages

    Returns:
        Tuple if an ``item``-like dict is found, else None.
    """
    # Direct simple shape: {art_url, title, artist}
    if isinstance(data, dict) and "art_url" in data:
        return (
            data.get("art_url"),
            data.get("title"),
            data.get("artist"),
        )

    # Unwrap common dealer wrappers recursively – breadth-first search for "item" / "track"
    # We try to be very tolerant because dealer payloads are undocumented and
    # vary between Spotify Web Player versions. REST uses {"item":{"name", "artists", "album":{"images"}}}
    # while Dealer Connect-State uses {"cluster":{"player_state":{"track":{"uri":"spotify:track:", "metadata":{"image_xlarge_url":...}}}}
    def _from_track_dict(track: dict) -> Tuple[str | None, str | None, str | None] | None:
        if not isinstance(track, dict):
            return None
        metadata = track.get("metadata") if isinstance(track.get("metadata"), dict) else {}
        # title
        title = track.get("name") or metadata.get("title") or track.get("title")
        # artist – dealer uses artist_name / metadata.artist_name / artists array
        artist: str | None = None
        if isinstance(track.get("artist_name"), str) and track.get("artist_name"):
            artist = track.get("artist_name")  # type: ignore[assignment]
        elif isinstance(metadata.get("artist_name"), str) and metadata.get("artist_name"):
            artist = metadata.get("artist_name")
        elif isinstance(track.get("artists"), list):
            names = [
                a.get("name", "") if isinstance(a, dict) else str(a)
                for a in track.get("artists", [])  # type: ignore[union-attr]
                if isinstance(a, (dict, str)) and (a.get("name") if isinstance(a, dict) else a)
            ]
            artist = ", ".join(n for n in names if n) if names else None
        elif isinstance(track.get("artist"), dict) and track.get("artist", {}).get("name"):
            artist = track["artist"]["name"]  # type: ignore[index]
        # art – try album.images first, then metadata image_*_url, then direct fields
        art_url: str | None = None
        album = track.get("album")
        if isinstance(album, dict):
            images = album.get("images") or []
            if images and isinstance(images[0], dict) and images[0].get("url"):
                art_url = images[0].get("url")
        if not art_url and metadata:
            for key in ("image_xlarge_url", "image_large_url", "image_url", "image_small_url"):
                val = metadata.get(key)
                if isinstance(val, str) and val.strip():
                    art_url = val.strip()
                    break
        if not art_url:
            for key in ("image_xlarge_url", "image_large_url", "image_url", "cover_url", "cover"):
                val = track.get(key)
                if isinstance(val, str) and val.strip():
                    art_url = val.strip()
                    break
        # Some dealer payloads store images as list under track.metadata.images or track.images
        if not art_url:
            for key in ("images",):
                val = track.get(key) or metadata.get(key)
                if isinstance(val, list) and val and isinstance(val[0], dict) and val[0].get("url"):
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
            # Spotify REST item shape
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

            # Dealer track shape: {"track": {...}} inside player_state / cluster
            if "track" in cur and isinstance(cur["track"], dict):
                extracted = _from_track_dict(cur["track"])
                if extracted:
                    return extracted

            # Bare track dict (itself looks like a track with uri + metadata)
            if isinstance(cur.get("uri"), str) and cur["uri"].startswith("spotify:track:"):
                extracted = _from_track_dict(cur)
                if extracted:
                    return extracted

            # Dealer cluster -> player_state
            for key in ("player_state", "cluster", "state", "result", "payload"):
                if key in cur and isinstance(cur[key], dict):
                    stack.append(cur[key])
            # payloads / updates arrays
            for key in ("payloads", "updates", "data", "clusters"):
                if key in cur and isinstance(cur[key], list):
                    stack.extend(cur[key])
            # Also traverse any dict values that look like track objects
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)

        elif isinstance(cur, list):
            stack.extend(cur)

    return None


def _parse_ws_message(
    raw: str | bytes,
) -> Tuple[str | None, str | None, str | None] | None:
    """Parse a raw WebSocket message into (art_url, title, artist).

    Returns None if the message is a heartbeat, ping, or unrecognized.
    """
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None
    raw = raw.strip()
    if not raw or raw in ("ping", "pong", '{"type":"ping"}', '{"type":"pong"}'):
        return None

    # Try JSON first
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    # Dealer sometimes sends {"headers":{}, "payloads":[...]} – extract directly
    if isinstance(data, dict) and "payloads" in data:
        # payloads is a list of JSON strings or dicts (or base64 protobuf for play-history)
        for p in data["payloads"]:
            if isinstance(p, str):
                try:
                    p_json = json.loads(p)
                    extracted = _extract_track_from_payload(p_json)
                    if extracted:
                        return extracted
                    # if json but not track, keep p as dict for fallback
                    p = p_json
                except json.JSONDecodeError:
                    # not JSON – keep raw string (likely base64 protobuf)
                    pass
            if isinstance(p, (dict, list)):
                extracted = _extract_track_from_payload(p)
                if extracted:
                    return extracted
        # fallback: try whole object
        return _extract_track_from_payload(data)

    return _extract_track_from_payload(data)


_TRACK_URI_RE = re.compile(r"spotify:track:([A-Za-z0-9]{22})")


def _extract_track_id_from_ws_raw(raw: str | bytes) -> str | None:
    """Extract a track id from a Dealer message where payloads are base64 protobuf.

    Example uri: hm://herodotus/uri/spotify:list:play-history:v1/...
    payloads[0] is base64 encoding of a protobuf that contains ascii
    ``spotify:track:<id>``. We decode and regex it. No REST polling here –
    this is a single track-id extraction triggered by a push event.
    """
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
        # try direct regex on raw string
        m = _TRACK_URI_RE.search(raw)
        return m.group(1) if m else None
    if not isinstance(data, dict):
        return None
    payloads = data.get("payloads")
    if isinstance(payloads, list):
        for p in payloads:
            if isinstance(p, str):
                # direct track uri in string?
                m = _TRACK_URI_RE.search(p)
                if m:
                    return m.group(1)
                # try base64 decode
                try:
                    # add padding
                    padded = p + "=" * (-len(p) % 4)
                    decoded = base64.b64decode(padded, validate=False)
                    text = decoded.decode("utf-8", errors="ignore")
                    m2 = _TRACK_URI_RE.search(text)
                    if m2:
                        return m2.group(1)
                    # also search raw bytes
                    m3 = _TRACK_URI_RE.search(decoded.decode("latin1", errors="ignore"))
                    if m3:
                        return m3.group(1)
                except Exception:
                    continue
    # fallback: search whole raw
    m = _TRACK_URI_RE.search(raw)
    return m.group(1) if m else None


def _fetch_track_sync(track_id: str, token: str) -> Tuple[str | None, str | None, str | None]:
    """Fetch a single track's (art_url, title, artist) via Spotify API – event-driven, not polling.

    Called only when Dealer push gives us a track id (e.g. play-history base64) but no
    artwork. This is a single GET triggered by the WebSocket event, not a poll loop.
    """
    t0 = time.perf_counter()
    log("api", f"[dim][api][/dim] fetch track {track_id} via API (push-triggered)")
    try:
        resp = requests.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        dt = (time.perf_counter() - t0) * 1000
        log("api", f"[dim][api][/dim] fetch track status={resp.status_code} took={dt:.0f}ms")
        if resp.status_code == 401:
            return (None, None, None)
        if not resp.ok:
            return (None, None, None)
        data = resp.json()
        title = data.get("name")
        artists = data.get("artists") or []
        artist: str | None = None
        if artists:
            names = [a.get("name", "") for a in artists if isinstance(a, dict) and a.get("name")]
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
        log("api", f"[dim][api][/dim] fetch track error took={dt:.0f}ms err={exc}")
        return (None, None, None)


def _fetch_current_playback_sync(
    token: str,
) -> Tuple[str | None, str | None, str | None] | None:
    """Fetch currently playing track once – for initial hydration only.

    This is a SINGLE GET to /v1/me/player/currently-playing called once at
    startup so the first track is shown immediately, before any Dealer push
    arrives. Not a poll loop; subsequent updates come via WebSocket.
    Returns (art_url, title, artist) or None if nothing playing / error.
    401 is signalled by returning None so caller can try refresh.
    """
    t0 = time.perf_counter()
    log("api", "[dim][api][/dim] fetch currently-playing (initial hydration)")
    try:
        resp = requests.get(
            SPOTIFY_CURRENTLY_PLAYING_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        dt = (time.perf_counter() - t0) * 1000
        log("api", f"[dim][api][/dim] currently-playing status={resp.status_code} took={dt:.0f}ms")
        if resp.status_code == 401:
            return None
        if resp.status_code == 204:
            # No content – nothing currently playing
            return None
        if resp.status_code == 404:
            return None
        if not resp.ok:
            return None
        # 200 – may be empty body if not playing (Spotify sometimes returns 200 with no item)
        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        # Rest shape uses "item"; _extract_track_from_payload handles it
        extracted = _extract_track_from_payload(data)
        if extracted:
            return extracted
        # Fallback: if is_playing is False, don't update hardware
        if data.get("is_playing") is False:
            return None
        return None
    except requests.RequestException as exc:
        dt = (time.perf_counter() - t0) * 1000
        log("api", f"[dim][api][/dim] currently-playing error took={dt:.0f}ms err={exc}")
        return None


# ---------------------------------------------------------------------------
# Main WebSocket watcher – pure push, no polling
# ---------------------------------------------------------------------------


async def watch_spotify_websocket(
    once: bool = False,
    reconnect_delay: float = 2.0,
    websocket_url: str | None = None,
    **kwargs,
) -> None:
    """Stream Spotify track changes over WebSocket (Dealer) – pure push.

    Connects to the Dealer WebSocket and processes track-change pushes.
    For ``once``, waits for a single push then exits. No polling.

        Spotify Server
             │
             │ track changed
             ▼
        WebSocket (Dealer)
             │
             ▼
        Spotify client → process_art_url

    Args:
        once: If True, handle one track event then return.
        reconnect_delay: Reconnect backoff base (seconds).
        websocket_url: Override WebSocket URL (e.g. for testing).
    """
    # Back-compat: old callers used poll_interval
    if "poll_interval" in kwargs and kwargs["poll_interval"] is not None:
        try:
            reconnect_delay = float(kwargs["poll_interval"])
        except (TypeError, ValueError):
            pass
    from .playerctl import process_art_url

    token = get_spotify_token()
    if not token:
        globs = Globs()
        config_path = getattr(globs, "config_path", None)
        token = ensure_valid_token(config_path=config_path)
        if not token:
            print(
                "[red bold]Error:[/red bold] Spotify API token not found. "
                "Cannot watch Spotify via WebSocket without authentication."
            )
            return

    globs = Globs()

    try:
        import websockets  # type: ignore[import]
        from websockets.exceptions import (  # type: ignore[import]
            ConnectionClosed,
            InvalidStatusCode,
        )
    except ImportError:
        print(
            "[red bold]Error:[/red bold] websockets package not installed – "
            "websocket-only mode requires websockets. "
            "Install with: pip install websockets"
        )
        return

    # Resolve custom URL from config if not passed explicitly
    if websocket_url is None:
        custom_cfg = getattr(globs, "spotify_websocket_url", None)
        if custom_cfg:
            websocket_url = custom_cfg

    last_art_url: str | None = None
    watch_t0 = time.perf_counter()
    delay = reconnect_delay
    max_delay = 30.0
    msg_count = 0

    log(
        "api",
        f"[dim][api][/dim] websocket watch start url={'custom' if websocket_url else 'dealer'} once={once} reconnect_delay={reconnect_delay}s",
    )

    # Initial hydration: single REST call so first track shows immediately
    # before any Dealer push arrives (e.g. app launched while track already playing).
    # Not a poll loop – pure push after this.
    try:
        current = await asyncio.to_thread(_fetch_current_playback_sync, token)
        if current is None:
            # Possible 401 – try token refresh once then retry
            try:
                refreshed = ensure_valid_token(config_path=getattr(globs, "config_path", None))
                if refreshed and refreshed != token:
                    token = refreshed
                    current = await asyncio.to_thread(_fetch_current_playback_sync, token)
            except Exception:
                pass
        if current is not None:
            art_url, title, artist = current
            if art_url:
                last_art_url = art_url
                song_label = ""
                if title and artist:
                    song_label = f"{title} – {artist}"
                elif title:
                    song_label = title
                elif artist:
                    song_label = artist
                else:
                    song_label = "Unknown track"
                print(f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...")
                init_t0 = time.perf_counter()
                await process_art_url(art_url)
                init_dt = (time.perf_counter() - init_t0) * 1000
                total_dt = (time.perf_counter() - watch_t0) * 1000
                log(
                    "api",
                    f"[dim][api][/dim] initial currently-playing processed art took={init_dt:.0f}ms total={total_dt:.0f}ms",
                )
                print("[bold green]Processing done[/bold green].")
                print("")
                if once:
                    return
            else:
                log("api", "[dim][api][/dim] initial currently-playing no artwork skip")
        else:
            log("api", "[dim][api][/dim] initial currently-playing nothing playing")
    except Exception as exc:
        log("api", f"[dim][api][/dim] initial currently-playing error err={exc}")

    while True:
        # Build URL with current token (token may have been refreshed)
        if websocket_url and "{token}" in websocket_url:
            ws_url = websocket_url.format(token=token)
        elif (
            websocket_url
            and "access_token" not in websocket_url
            and websocket_url.startswith("wss://")
        ):
            # Custom base without token – append
            sep = "&" if "?" in websocket_url else "?"
            ws_url = (
                f"{websocket_url}{sep}access_token={urllib.parse.quote(token, safe='')}"
            )
        elif websocket_url:
            ws_url = websocket_url
        else:
            ws_url = _build_websocket_url(token)

        log(
            "api",
            f"[dim][api][/dim] websocket connect attempt delay={delay:.1f}s",
        )
        try:
            # Dealer expects browser-like Origin; helps avoid 403 on some networks
            dealer_headers = {
                "Origin": "https://open.spotify.com",
                "User-Agent": "Mozilla/5.0 BeatBoard/0.1.3",
            }
            try:
                ws_ctx = websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                    additional_headers=dealer_headers,
                )
            except TypeError:
                # websockets <14 uses extra_headers
                ws_ctx = websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                    extra_headers=dealer_headers,  # type: ignore[call-arg]
                )
            async with ws_ctx as ws:
                log(
                    "api",
                    f"[dim][api][/dim] websocket connected total={(time.perf_counter() - watch_t0) * 1000:.0f}ms",
                )
                delay = reconnect_delay  # reset on successful connect
                async for raw_msg in ws:
                    msg_count += 1
                    iter_t0 = time.perf_counter()
                    try:
                        preview = (
                            raw_msg
                            if isinstance(raw_msg, str)
                            else raw_msg.decode("utf-8", errors="ignore")  # type: ignore[union-attr]
                        )
                    except Exception:
                        preview = str(raw_msg)[:500]
                    # Always show raw frame when api/all debug is on – truncated to keep logs readable
                    log(
                        "api",
                        f"[dim][api][/dim] websocket raw #{msg_count} {preview[:800]!r}",
                    )
                    parsed = _parse_ws_message(raw_msg)  # type: ignore[arg-type]
                    if parsed is None:
                        # Dealer play-history messages carry track uri as base64 protobuf
                        # with no artwork – fetch single track via API (push-triggered, not polling)
                        track_id = _extract_track_id_from_ws_raw(raw_msg)  # type: ignore[arg-type]
                        if track_id:
                            log(
                                "api",
                                f"[dim][api][/dim] websocket msg #{msg_count} play-history track={track_id} → fetch track",
                            )
                            try:
                                fetched = await asyncio.to_thread(
                                    _fetch_track_sync, track_id, token
                                )
                            except Exception as exc:
                                log(
                                    "api",
                                    f"[dim][api][/dim] websocket msg #{msg_count} fetch error err={exc} iter={(time.perf_counter() - iter_t0) * 1000:.0f}ms",
                                )
                                continue
                            art_fetched, title_fetched, artist_fetched = fetched
                            # handle 401 – try token refresh once
                            if art_fetched is None and title_fetched is None:
                                # check if token refresh helps (fetch returned 401)
                                try:
                                    refreshed = ensure_valid_token(
                                        config_path=getattr(globs, "config_path", None)
                                    )
                                    if refreshed and refreshed != token:
                                        token = refreshed
                                        fetched = await asyncio.to_thread(
                                            _fetch_track_sync, track_id, token
                                        )
                                        art_fetched, title_fetched, artist_fetched = fetched
                                except Exception:
                                    pass
                            if not art_fetched:
                                log(
                                    "api",
                                    f"[dim][api][/dim] websocket msg #{msg_count} fetch no artwork skip iter={(time.perf_counter() - iter_t0) * 1000:.0f}ms",
                                )
                                continue
                            parsed = (art_fetched, title_fetched, artist_fetched)
                        else:
                            # Check for dealer ping/heartbeat that isn't JSON track data
                            # Dealer sends {"type":"ping"} – reply with pong
                            try:
                                maybe = (
                                    json.loads(raw_msg)
                                    if isinstance(raw_msg, (str, bytes))
                                    else None
                                )
                                if isinstance(maybe, dict) and maybe.get("type") == "ping":
                                    await ws.send(json.dumps({"type": "pong"}))
                                    log("api", "[dim][api][/dim] websocket ping→pong")
                                    continue
                            except Exception:
                                pass
                            log(
                                "api",
                                f"[dim][api][/dim] websocket msg #{msg_count} unparsed/heartbeat skip iter={(time.perf_counter() - iter_t0) * 1000:.0f}ms",
                            )
                            continue

                    art_url, title, artist = parsed
                    if not art_url:
                        log(
                            "api",
                            f"[dim][api][/dim] websocket msg #{msg_count} no artwork skip",
                        )
                        continue
                    if art_url == last_art_url:
                        log(
                            "api",
                            f"[dim][api][/dim] websocket msg #{msg_count} unchanged art skip iter={(time.perf_counter() - iter_t0) * 1000:.0f}ms",
                        )
                        continue

                    song_label = ""
                    if title and artist:
                        song_label = f"{title} – {artist}"
                    elif title:
                        song_label = title
                    elif artist:
                        song_label = artist
                    else:
                        song_label = "Unknown track"

                    print(
                        f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                    )
                    proc_t0 = time.perf_counter()
                    await process_art_url(art_url)
                    proc_dt = (time.perf_counter() - proc_t0) * 1000
                    iter_dt = (time.perf_counter() - iter_t0) * 1000
                    total_dt = (time.perf_counter() - watch_t0) * 1000
                    log(
                        "api",
                        f"[dim][api][/dim] websocket msg #{msg_count} processed art took={proc_dt:.0f}ms iter={iter_dt:.0f}ms total={total_dt:.0f}ms",
                    )
                    print("[bold green]Processing done[/bold green].")
                    print("")
                    last_art_url = art_url
                    if once:
                        return

        except (
            ConnectionClosed,
            InvalidStatusCode,
            OSError,
            asyncio.TimeoutError,
        ) as exc:  # type: ignore[attr-defined]
            dt = (time.perf_counter() - watch_t0) * 1000
            log(
                "api",
                f"[dim][api][/dim] websocket disconnected total={dt:.0f}ms err={exc} reconnect in {delay:.1f}s",
            )
            # Auth errors – try token refresh before reconnect
            if (
                "401" in str(exc)
                or "403" in str(exc)
                or isinstance(exc, InvalidStatusCode)
                and getattr(exc, "status_code", None) in (401, 403)
            ):  # type: ignore[attr-defined]
                print(
                    f"[yellow]Warning:[/yellow] WebSocket auth failed ({exc}) – refreshing token…"
                )
                try:
                    refreshed = ensure_valid_token(
                        config_path=getattr(globs, "config_path", None)
                    )
                    if refreshed and refreshed != token:
                        token = refreshed
                        delay = reconnect_delay
                        continue
                except Exception as refresh_exc:  # pragma: no cover
                    print(f"[bold red]Error:[/bold red] Refresh failed: {refresh_exc}")
            # Quiet in normal run – use --debug api to see reconnects
            log(
                "api",
                f"[dim][api][/dim] websocket reconnect scheduled in {delay:.1f}s",
            )
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, max_delay)
            continue
        except Exception as exc:  # pragma: no cover
            log(
                "api",
                f"[dim][api][/dim] websocket unexpected error total={(time.perf_counter() - watch_t0) * 1000:.0f}ms err={exc}",
            )
            # websocket-only – just reconnect, no polling fallback
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, max_delay)
            continue


async def watch_spotify_api(
    once: bool = False,
    reconnect_delay: float = 2.0,
    **kwargs,
) -> None:
    """Stream Spotify track changes and update hardware lighting.

    Pure WebSocket push – no polling.

    This is the user-facing entry point; ``watch_spotify_websocket`` is
    the underlying implementation. Both names are kept for compatibility.

    Args:
        once: If True, wait for one track event then return.
        reconnect_delay: Reconnect backoff base (seconds).
    """
    if "poll_interval" in kwargs and kwargs["poll_interval"] is not None:
        try:
            reconnect_delay = float(kwargs["poll_interval"])
        except (TypeError, ValueError):
            pass
    await watch_spotify_websocket(once=once, reconnect_delay=reconnect_delay)


# Backwards compatibility aliases: issue title uses --spotify, prompt uses --api
watch_spotify = watch_spotify_api
watch_spotify_ws = watch_spotify_websocket
check_spotify_available_api = check_spotify_api_available
get_token = get_spotify_token
