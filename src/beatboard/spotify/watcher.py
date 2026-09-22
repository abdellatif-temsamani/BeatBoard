"""WebSocket watcher – pure push via Spotify Dealer."""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.parse

from rich import print

from ..globs import Globs
from ..logs import log
from .api import _fetch_current_playback_sync, _fetch_track_sync
from .auth import _try_refresh_token, ensure_valid_token, get_spotify_token
from .constants import SPOTIFY_DEALER_WS_URL, _UNAUTHORIZED
from .parsing import _extract_track_and_art_from_ws_raw, _parse_ws_message


def _build_websocket_url(token: str) -> str:
    """Build the Spotify WebSocket (Dealer) URL."""
    globs = Globs()
    custom = getattr(globs, "spotify_websocket_url", None) or os.getenv(
        "SPOTIFY_WEBSOCKET_URL"
    )
    if custom:
        custom = custom.strip()
        if custom:
            if "{token}" in custom:
                return custom.format(token=token)
            if "access_token" not in custom:
                sep = "&" if "?" in custom else "?"
                return f"{custom}{sep}access_token={urllib.parse.quote(token, safe='')}"
            return custom
    return SPOTIFY_DEALER_WS_URL.format(token=urllib.parse.quote(token, safe=""))


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
    from ..playerctl import process_art_url

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
    last_track_id: str | None = None
    delay = reconnect_delay
    max_delay = 30.0
    msg_count = 0

    log(
        "api",
        f"[cyan]api[/cyan] [dim]·[/dim] [blue]ws[/blue] watch start [dim]·[/dim] {'[magenta]custom[/magenta]' if websocket_url else '[green]dealer[/green]'} [dim]·[/dim] reconnect [cyan]{reconnect_delay:.1f}s[/cyan]"
        + (" [dim]·[/dim] [yellow]once[/yellow]" if once else ""),
    )

    # Initial hydration: single REST call so first track shows immediately
    # before any Dealer push arrives (e.g. app launched while track already playing).
    # Not a poll loop – pure push after this.
    try:
        current = await asyncio.to_thread(_fetch_current_playback_sync, token)
        if current is _UNAUTHORIZED:
            # 401 – token expired, force refresh then retry once
            log("api", "[yellow]api[/yellow] [dim]·[/dim] now playing 401, refreshing…")
            try:
                refreshed = ensure_valid_token(
                    config_path=getattr(globs, "config_path", None),
                    force_refresh=True,
                )
                if refreshed and refreshed != token:
                    token = refreshed
                    current = await asyncio.to_thread(
                        _fetch_current_playback_sync, token
                    )
                    if current is not None and current is not _UNAUTHORIZED:
                        log(
                            "api",
                            "[green]api[/green] [dim]·[/dim] now playing retry after refresh [green]ok[/green]",
                        )
                    elif current is _UNAUTHORIZED:
                        log(
                            "api",
                            "[red]api[/red] [dim]·[/dim] still 401 after refresh",
                        )
                        current = None
                    else:
                        # Refresh succeeded but still empty – handled as nothing playing
                        pass
                elif refreshed and refreshed == token:
                    # Force refresh returned same token (unlikely) – still retry once
                    current = await asyncio.to_thread(
                        _fetch_current_playback_sync, token
                    )
                    if current is _UNAUTHORIZED:
                        current = None
                else:
                    # No refreshed token – cannot recover
                    current = None
            except Exception:
                current = None
        if current is not None and current is not _UNAUTHORIZED:
            art_url, title, artist = current  # type: ignore[misc]
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
                print(
                    f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                )
                try:
                    from ..plugins.hooks import run_extension_hooks

                    run_extension_hooks(
                        "track_change",
                        title=title or "",
                        artist=artist or "",
                        art_url=art_url or "",
                    )
                except Exception:
                    pass
                init_t0 = time.perf_counter()
                await process_art_url(art_url)
                init_dt = (time.perf_counter() - init_t0) * 1000
                log(
                    "api",
                    f"[blue]ws[/blue] [dim]·[/dim] initial [green]{song_label}[/green] [dim]·[/dim] [cyan]{init_dt:.0f}ms[/cyan]",
                )
                print("[bold green]Processing done[/bold green].")
                print("[dim]" + "─" * 50 + "[/dim]")
                print("")
                if once:
                    return
            else:
                log("api", "[yellow]ws[/yellow] [dim]·[/dim] initial no artwork, skip")
        else:
            log("api", "[blue]ws[/blue] [dim]·[/dim] initial nothing playing")
    except Exception as exc:
        log("api", f"[red]ws[/red] [dim]·[/dim] initial error: {exc}")

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

        if delay != reconnect_delay:
            log(
                "api",
                f"[yellow]ws[/yellow] [dim]·[/dim] connecting… [dim](retry in [yellow]{delay:.1f}s[/yellow])[/dim]",
            )
        else:
            log("api", "[blue]ws[/blue] [dim]·[/dim] connecting…")
        pending_task: asyncio.Task | None = None
        try:
            # Dealer expects browser-like Origin; helps avoid 403 on some networks
            dealer_headers = {
                "Origin": "https://open.spotify.com",
                "User-Agent": "Mozilla/5.0 BeatBoard/0.3.0",
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
                log("api", "[green]ws[/green] [dim]·[/dim] [green]connected[/green]")
                delay = reconnect_delay  # reset on successful connect
                pending_task = None

                async def _process_resolved_art(
                    art_url: str,
                    title: str | None,
                    artist: str | None,
                    track_id: str | None,
                    song_label: str,
                ) -> None:
                    nonlocal last_art_url, last_track_id
                    try:
                        from ..plugins.hooks import run_extension_hooks

                        run_extension_hooks(
                            "track_change",
                            title=title or "",
                            artist=artist or "",
                            art_url=art_url or "",
                            track_id=track_id or "",
                        )
                    except Exception:
                        pass
                    proc_t0 = time.perf_counter()
                    try:
                        await process_art_url(art_url, track_id=track_id)
                    except asyncio.CancelledError:
                        log(
                            "api",
                            f"[yellow]ws[/yellow] [dim]·[/dim] cancelled [white]{song_label}[/white]",
                        )
                        raise
                    except Exception as exc:
                        log(
                            "api",
                            f"[red]ws[/red] [dim]·[/dim] process failed [white]{song_label}[/white] [red]{exc}[/red]",
                        )
                        return
                    proc_dt = (time.perf_counter() - proc_t0) * 1000
                    log(
                        "api",
                        f"[blue]ws[/blue] [dim]·[/dim] [green]{song_label}[/green] [dim]·[/dim] [cyan]{proc_dt:.0f}ms[/cyan]",
                    )
                    last_art_url = art_url
                    if track_id:
                        last_track_id = track_id

                async for raw_msg in ws:
                    msg_count += 1
                    parsed = _parse_ws_message(raw_msg)  # type: ignore[arg-type]
                    _pending_track_id: str | None = None
                    if parsed is None:
                        track_id, art_url_ws = _extract_track_and_art_from_ws_raw(
                            raw_msg  # type: ignore[arg-type]
                        )
                        _pending_track_id = track_id
                        if track_id:
                            if track_id == last_track_id:
                                log(
                                    "api",
                                    "[blue]ws[/blue] [dim]· unchanged, skip[/dim]",
                                )
                                continue
                            from ..cache.colors import (
                                get_cached_colors_by_track_id as _track_get,
                            )
                            from ..playerctl import apply_colors as _apply_colors

                            cached_preview = _track_get(track_id)
                            if cached_preview is not None:
                                song_label = f"{track_id[:8]}… (cache)"
                                last_track_id = track_id
                                last_art_url = art_url_ws or f"track_{track_id}"
                                log(
                                    "api",
                                    f"[green]ws[/green] [dim]·[/dim] track [white]{track_id[:8]}…[/white] [green]cache hit[/green] [dim]track_id[/dim]",
                                )
                                print(
                                    f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                                )

                                async def _cache_hit_task(
                                    tid=track_id,
                                    aw=art_url_ws,
                                    cached=cached_preview,
                                    label=song_label,
                                ):
                                    nonlocal last_art_url, last_track_id
                                    try:
                                        try:
                                            from ..plugins.hooks import (
                                                run_extension_hooks as _reh,
                                            )

                                            _reh(
                                                "track_change",
                                                title="",
                                                artist="",
                                                art_url=aw or "",
                                                track_id=tid or "",
                                            )
                                        except Exception:
                                            pass
                                        proc_t0 = time.perf_counter()
                                        await _apply_colors(cached)
                                        try:
                                            from ..plugins.hooks import (
                                                run_extension_hooks as _reh2,
                                            )

                                            _reh2(
                                                "color_applied",
                                                color=cached[0] if cached else "ffffff",
                                                art_url=aw or "",
                                                track_id=tid or "",
                                            )
                                        except Exception:
                                            pass
                                        proc_dt = (time.perf_counter() - proc_t0) * 1000
                                        log(
                                            "api",
                                            f"[blue]ws[/blue] [dim]·[/dim] [green]{label}[/green] [dim]·[/dim] [cyan]{proc_dt:.0f}ms[/cyan]",
                                        )
                                        print(
                                            "[bold green]Processing done[/bold green]."
                                        )
                                        print("[dim]" + "─" * 50 + "[/dim]")
                                        print("")
                                        last_track_id = tid
                                        last_art_url = aw or f"track_{tid}"
                                    except asyncio.CancelledError:
                                        log(
                                            "api",
                                            f"[yellow]ws[/yellow] [dim]·[/dim] cancelled [white]{label}[/white]",
                                        )
                                        raise
                                    except Exception as exc:
                                        log(
                                            "api",
                                            f"[red]ws[/red] [dim]·[/dim] cache apply failed [red]{exc}[/red]",
                                        )

                                if once:
                                    await _cache_hit_task()
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(_cache_hit_task())
                                continue
                            if art_url_ws:
                                if art_url_ws == last_art_url:
                                    log(
                                        "api",
                                        "[blue]ws[/blue] [dim]· unchanged, skip[/dim]",
                                    )
                                    continue
                                song_label = f"{track_id[:8]}…"
                                last_track_id = track_id
                                last_art_url = art_url_ws
                                print(
                                    f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                                )

                                async def _art_task(
                                    aw=art_url_ws, tid=track_id, label=song_label
                                ):
                                    try:
                                        await _process_resolved_art(
                                            aw, None, None, tid, label
                                        )
                                        print(
                                            "[bold green]Processing done[/bold green]."
                                        )
                                        print("[dim]" + "─" * 50 + "[/dim]")
                                        print("")
                                    except asyncio.CancelledError:
                                        raise

                                if once:
                                    await _art_task()
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(_art_task())
                                continue
                            else:
                                song_label = f"{track_id[:8]}…"
                                last_track_id = track_id
                                print(
                                    f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                                )
                                log(
                                    "api",
                                    f"[blue]ws[/blue] [dim]·[/dim] track [white]{track_id[:8]}…[/white] [dim]→[/dim] [yellow]fetch[/yellow]",
                                )

                                async def _fetch_task(tid=track_id, label=song_label):
                                    nonlocal token, last_art_url, last_track_id
                                    try:
                                        fetched = await asyncio.to_thread(
                                            _fetch_track_sync, tid, token
                                        )
                                    except Exception as exc:
                                        log(
                                            "api",
                                            f"[red]ws[/red] [dim]·[/dim] fetch failed: [red]{exc}[/red]",
                                        )
                                        try:
                                            print(
                                                "[bold green]Processing done[/bold green]."
                                            )
                                            print("[dim]" + "─" * 50 + "[/dim]")
                                            print("")
                                        except Exception:
                                            pass
                                        return
                                    art_fetched, title_fetched, artist_fetched = fetched
                                    if art_fetched is None and title_fetched is None:
                                        try:
                                            refreshed = _try_refresh_token(
                                                config_path=getattr(
                                                    globs, "config_path", None
                                                )
                                            )
                                            if refreshed and refreshed != token:
                                                token = refreshed
                                                fetched = await asyncio.to_thread(
                                                    _fetch_track_sync, tid, token
                                                )
                                                (
                                                    art_fetched,
                                                    title_fetched,
                                                    artist_fetched,
                                                ) = fetched
                                        except Exception:
                                            pass
                                    if not art_fetched:
                                        log(
                                            "api",
                                            "[yellow]ws[/yellow] [dim]·[/dim] no artwork, skip",
                                        )
                                        try:
                                            print(
                                                "[bold green]Processing done[/bold green]."
                                            )
                                            print("[dim]" + "─" * 50 + "[/dim]")
                                            print("")
                                        except Exception:
                                            pass
                                        return
                                    better_label = label
                                    if title_fetched and artist_fetched:
                                        better_label = (
                                            f"{title_fetched} – {artist_fetched}"
                                        )
                                    elif title_fetched:
                                        better_label = title_fetched
                                    await _process_resolved_art(
                                        art_fetched,
                                        title_fetched,
                                        artist_fetched,
                                        tid,
                                        better_label,
                                    )
                                    try:
                                        print(
                                            "[bold green]Processing done[/bold green]."
                                        )
                                        print("[dim]" + "─" * 50 + "[/dim]")
                                        print("")
                                    except Exception:
                                        pass

                                if once:
                                    await _fetch_task()
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(_fetch_task())
                                continue
                        else:
                            try:
                                maybe = (
                                    json.loads(raw_msg)
                                    if isinstance(raw_msg, (str, bytes))
                                    else None
                                )
                                if (
                                    isinstance(maybe, dict)
                                    and maybe.get("type") == "ping"
                                ):
                                    await ws.send(json.dumps({"type": "pong"}))
                                    log(
                                        "api",
                                        "[cyan]ws[/cyan] [dim]·[/dim] ping[dim]↔[/dim]pong",
                                    )
                                    continue
                            except Exception:
                                pass
                            if art_url_ws:
                                if art_url_ws == last_art_url:
                                    log(
                                        "api",
                                        "[blue]ws[/blue] [dim]· unchanged, skip[/dim]",
                                    )
                                    continue
                                song_label = "Unknown track"
                                last_art_url = art_url_ws
                                print(
                                    f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                                )

                                async def _bare_art_task(
                                    aw=art_url_ws, label=song_label
                                ):
                                    try:
                                        await _process_resolved_art(
                                            aw, None, None, None, label
                                        )
                                        print(
                                            "[bold green]Processing done[/bold green]."
                                        )
                                        print("[dim]" + "─" * 50 + "[/dim]")
                                        print("")
                                    except asyncio.CancelledError:
                                        raise

                                if once:
                                    await _bare_art_task()
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(_bare_art_task())
                                continue
                            else:
                                log("api", "[blue]ws[/blue] [dim]· heartbeat[/dim]")
                                continue
                    art_url, title, artist = parsed
                    if not art_url:
                        log("api", "[yellow]ws[/yellow] [dim]·[/dim] no artwork, skip")
                        continue
                    if art_url == last_art_url:
                        log("api", "[blue]ws[/blue] [dim]· unchanged, skip[/dim]")
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
                        if _pending_track_id:
                            song_label = f"{_pending_track_id[:8]}…"
                    last_art_url = art_url
                    if _pending_track_id:
                        last_track_id = _pending_track_id
                    print(
                        f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                    )

                    async def _parsed_task(
                        au=art_url,
                        ti=title,
                        ar=artist,
                        tid=_pending_track_id,
                        label=song_label,
                    ):
                        try:
                            await _process_resolved_art(au, ti, ar, tid, label)
                            print("[bold green]Processing done[/bold green].")
                            print("[dim]" + "─" * 50 + "[/dim]")
                            print("")
                        except asyncio.CancelledError:
                            raise

                    if once:
                        await _parsed_task()
                        return
                    if pending_task and not pending_task.done():
                        pending_task.cancel()
                    pending_task = asyncio.create_task(_parsed_task())

        except (
            ConnectionClosed,
            InvalidStatusCode,
            OSError,
            asyncio.TimeoutError,
        ) as exc:  # type: ignore[attr-defined]
            try:
                if pending_task is not None and not pending_task.done():
                    pending_task.cancel()
            except Exception:
                pass
            log(
                "api",
                f"[yellow]ws[/yellow] [dim]·[/dim] disconnected [dim]({exc})[/dim] [dim]·[/dim] retry in [yellow]{delay:.1f}s[/yellow]",
            )
            _status = getattr(exc, "status_code", None)
            is_auth = (
                "401" in str(exc)
                or "403" in str(exc)
                or _status in (401, 403)
                or (
                    isinstance(exc, InvalidStatusCode)
                    and getattr(exc, "status_code", None) in (401, 403)
                )
            )
            if is_auth:  # type: ignore[attr-defined]
                print(
                    f"[yellow]Warning:[/yellow] WebSocket auth failed ({exc}) – refreshing token…"
                )
                try:
                    refreshed = _try_refresh_token(
                        config_path=getattr(globs, "config_path", None)
                    )
                    if not refreshed:
                        refreshed = ensure_valid_token(
                            config_path=getattr(globs, "config_path", None),
                            force_refresh=True,
                        )
                    if refreshed and refreshed != token:
                        token = refreshed
                        delay = reconnect_delay
                        log(
                            "api",
                            "[green]ws[/green] [dim]·[/dim] token refreshed, reconnecting…",
                        )
                        continue
                except Exception as refresh_exc:  # pragma: no cover
                    print(f"[bold red]Error:[/bold red] Refresh failed: {refresh_exc}")
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, max_delay)
            continue
        except Exception as exc:  # pragma: no cover
            try:
                if pending_task is not None and not pending_task.done():
                    pending_task.cancel()
            except Exception:
                pass
            log(
                "api",
                f"[red]ws[/red] [dim]·[/dim] [red]error[/red]: {exc} [dim]·[/dim] retry in [yellow]{delay:.1f}s[/yellow]",
            )
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, max_delay)
            continue


async def watch_spotify_api(
    once: bool = False,
    reconnect_delay: float = 2.0,
    **kwargs,
) -> None:
    """Stream Spotify track changes and update hardware lighting."""
    if "poll_interval" in kwargs and kwargs["poll_interval"] is not None:
        try:
            reconnect_delay = float(kwargs["poll_interval"])
        except (TypeError, ValueError):
            pass
    await watch_spotify_websocket(once=once, reconnect_delay=reconnect_delay)
