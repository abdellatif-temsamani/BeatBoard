"""Spotify diagnostics – tokens, playerctl, API."""

from __future__ import annotations

import shutil
import subprocess


def diagnose_spotify() -> list[dict[str, str]]:
    """Check Spotify integration health (config-only, no env vars)."""
    results: list[dict[str, str]] = []

    # Globs tokens (config only)
    try:
        from beatboard.globs import Globs

        globs = Globs()
        token = getattr(globs, "spotify_token", None)
        refresh = getattr(globs, "spotify_refresh_token", None)
        client_id = getattr(globs, "spotify_client_id", None)
        client_secret = getattr(globs, "spotify_client_secret", None)
        redirect = getattr(globs, "spotify_redirect_uri", None)
        ws_url = getattr(globs, "spotify_websocket_url", None)

        results.append(
            {
                "check": "spotify_token (config)",
                "status": "ok" if token else "info",
                "detail": f"{len(token)} chars masked" if token else "not set",
                "hint": "" if token else "Add spotify_token to config.yaml or run --api",
            }
        )
        results.append(
            {
                "check": "refresh_token (config)",
                "status": "ok" if refresh else "info",
                "detail": "set" if refresh else "not set",
                "hint": "" if refresh else "OAuth flow will obtain it",
            }
        )
        results.append(
            {
                "check": "Spotify client_id",
                "status": "ok" if client_id else "warn",
                "detail": f"{client_id[:6]}… ({len(client_id)} chars)" if client_id else "not set",
                "hint": "" if client_id else "Create app at https://developer.spotify.com/dashboard",
            }
        )
        results.append(
            {
                "check": "Spotify client_secret",
                "status": "ok" if client_secret else "warn",
                "detail": "set" if client_secret else "not set",
                "hint": "" if client_secret else "Required for --api refresh/OAuth",
            }
        )
        if redirect:
            results.append(
                {
                    "check": "Redirect URI",
                    "status": "ok",
                    "detail": redirect,
                    "hint": "",
                }
            )
        if ws_url:
            results.append({"check": "WebSocket URL", "status": "ok", "detail": ws_url, "hint": ""})
    except Exception as exc:
        results.append(
            {
                "check": "Globs spotify config",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # get_spotify_token helper (config-only)
    try:
        from beatboard.spotify import get_spotify_token

        t = get_spotify_token()
        results.append(
            {
                "check": "Resolved token (get_spotify_token)",
                "status": "ok" if t else "warn",
                "detail": f"found ({len(t)} chars)" if t else "none – will need OAuth",
                "hint": "" if t else "Run `beatboard --api` to start browser OAuth",
            }
        )
    except Exception as exc:
        results.append(
            {
                "check": "Resolved token",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # playerctl
    which_pc = shutil.which("playerctl")
    results.append(
        {
            "check": "playerctl binary",
            "status": "ok" if which_pc else "warn",
            "detail": which_pc or "not found in PATH",
            "hint": "" if which_pc else "Install: apt install playerctl / dnf install playerctl",
        }
    )
    if which_pc:
        try:
            from beatboard.playerctl import check_spotify_available

            avail = check_spotify_available()
            results.append(
                {
                    "check": "Spotify via playerctl",
                    "status": "ok" if avail else "warn",
                    "detail": "spotify player found" if avail else "spotify not in `playerctl --list-all`",
                    "hint": "" if avail else "Ensure Spotify Desktop is running",
                }
            )
            try:
                out = subprocess.run(
                    ["playerctl", "--list-all"],
                    capture_output=True,
                    text=True,
                    timeout=3,
                )
                detail = out.stdout.strip() or "(no players)"
                if out.returncode != 0:
                    detail += f" stderr: {out.stderr.strip()}"
                results.append(
                    {
                        "check": "playerctl --list-all",
                        "status": "ok",
                        "detail": detail,
                        "hint": "",
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "check": "playerctl --list-all",
                        "status": "warn",
                        "detail": str(exc),
                        "hint": "",
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "check": "Spotify via playerctl",
                    "status": "warn",
                    "detail": str(exc),
                    "hint": "",
                }
            )
    else:
        results.append(
            {
                "check": "Spotify via playerctl",
                "status": "info",
                "detail": "skipped – playerctl missing (use --api on Windows/macOS)",
                "hint": "Install playerctl on Linux or use `beatboard --api`",
            }
        )

    # Spotify API check – config-only
    try:
        from beatboard.globs import Globs as _G
        from beatboard.spotify import get_spotify_token as _get_token

        _tok = None
        try:
            _tok = _get_token()
        except Exception:
            _tok = None
        try:
            _g2 = _G()
            _cid = getattr(_g2, "spotify_client_id", None)
            _csec = getattr(_g2, "spotify_client_secret", None)
        except Exception:
            _cid = None
            _csec = None
        api_ok = bool(_tok or (_cid and _csec))
        results.append(
            {
                "check": "Spotify API available",
                "status": "ok" if api_ok else "warn",
                "detail": "token or OAuth credentials present" if api_ok else "no token and no client credentials",
                "hint": "" if api_ok else "Set spotify_token or client_id/secret in config.yaml and run --api",
            }
        )
    except Exception as exc:
        results.append(
            {
                "check": "Spotify API available",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # WebSocket lib
    try:
        import websockets  # type: ignore

        ver = getattr(websockets, "__version__", "unknown")
        results.append({"check": "websockets lib", "status": "ok", "detail": f"v{ver}", "hint": ""})
    except Exception as exc:
        results.append(
            {
                "check": "websockets lib",
                "status": "fail",
                "detail": f"missing: {exc}",
                "hint": "pip install websockets",
            }
        )

    # requests
    try:
        import requests  # type: ignore

        results.append(
            {
                "check": "requests lib",
                "status": "ok",
                "detail": f"v{requests.__version__}",
                "hint": "",
            }
        )
    except Exception as exc:
        results.append(
            {
                "check": "requests lib",
                "status": "fail",
                "detail": str(exc),
                "hint": "pip install requests",
            }
        )

    return results
