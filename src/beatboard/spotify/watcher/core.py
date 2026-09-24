"""Core WebSocket watcher – pure push, no polling."""

from __future__ import annotations

import asyncio
import json

from rich import print

from ...globs import Globs
from ...logs import log
from ..auth import _try_refresh_token, ensure_valid_token, get_spotify_token
from ..parsing import _extract_track_and_art_from_ws_raw, _parse_ws_message
from .connection import _DEALER_HEADERS, _resolve_websocket_url
from .handlers import (
    _art_task,
    _bare_art_task,
    _cache_hit_task,
    _fetch_task,
    _parsed_task,
)
from .hydration import _hydrate_initial


class _WatcherState:
    """Mutable watcher state shared with handlers."""

    def __init__(self, token: str, globs: Globs) -> None:
        self.token = token
        self.globs = globs
        self.last_art_url: str | None = None
        self.last_track_id: str | None = None


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
    if 'poll_interval' in kwargs and kwargs['poll_interval'] is not None:
        try:
            reconnect_delay = float(kwargs['poll_interval'])
        except (TypeError, ValueError):
            pass

    token = get_spotify_token()
    if not token:
        globs = Globs()
        config_path = getattr(globs, 'config_path', None)
        token = ensure_valid_token(config_path=config_path)
        if not token:
            print(
                '[red bold]Error:[/red bold] Spotify API token not found. '
                'Cannot watch Spotify via WebSocket without authentication.'
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
            '[red bold]Error:[/red bold] websockets package not installed – '
            'websocket-only mode requires websockets. '
            'Install with: pip install websockets'
        )
        return

    if websocket_url is None:
        custom_cfg = getattr(globs, 'spotify_websocket_url', None)
        if custom_cfg:
            websocket_url = custom_cfg

    state = _WatcherState(token, globs)
    delay = reconnect_delay
    max_delay = 30.0
    msg_count = 0

    log(
        'api',
        f'[cyan]api[/cyan] [dim]·[/dim] [blue]ws[/blue] watch start [dim]·[/dim] '
        f'{"[magenta]custom[/magenta]" if websocket_url else "[green]dealer[/green]"} '
        f'[dim]·[/dim] reconnect [cyan]{reconnect_delay:.1f}s[/cyan]'
        + (' [dim]·[/dim] [yellow]once[/yellow]' if once else ''),
    )

    # Initial hydration – single REST call before push.
    new_token, last_art, should_exit = await _hydrate_initial(state.token, globs, once)
    state.token = new_token
    if last_art:
        state.last_art_url = last_art
    if should_exit:
        return

    while True:
        ws_url = _resolve_websocket_url(state.token, websocket_url)

        if delay != reconnect_delay:
            log(
                'api',
                f'[yellow]ws[/yellow] [dim]·[/dim] connecting… [dim](retry in [yellow]{delay:.1f}s[/yellow])[/dim]',
            )
        else:
            log('api', '[blue]ws[/blue] [dim]·[/dim] connecting…')
        pending_task: asyncio.Task | None = None
        try:
            dealer_headers = dict(_DEALER_HEADERS)
            try:
                ws_ctx = websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                    additional_headers=dealer_headers,
                )
            except TypeError:
                ws_ctx = websockets.connect(
                    ws_url,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=5,
                    extra_headers=dealer_headers,  # type: ignore[call-arg]
                )
            async with ws_ctx as ws:
                log('api', '[green]ws[/green] [dim]·[/dim] [green]connected[/green]')
                delay = reconnect_delay
                pending_task = None

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
                            if track_id == state.last_track_id:
                                log(
                                    'api',
                                    '[blue]ws[/blue] [dim]· unchanged, skip[/dim]',
                                )
                                continue
                            from ...cache.colors import (
                                get_cached_colors_by_track_id as _track_get,
                            )

                            cached_preview = _track_get(track_id)
                            if cached_preview is not None:
                                song_label = f'{track_id[:8]}… (cache)'
                                state.last_track_id = track_id
                                state.last_art_url = art_url_ws or f'track_{track_id}'
                                log(
                                    'api',
                                    f'[green]ws[/green] [dim]·[/dim] track [white]{track_id[:8]}…[/white] [green]cache hit[/green] [dim]track_id[/dim]',
                                )
                                print(
                                    f'[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...'
                                )
                                if once:
                                    await _cache_hit_task(
                                        track_id,
                                        art_url_ws,
                                        cached_preview,
                                        song_label,
                                        state,
                                    )
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(
                                    _cache_hit_task(
                                        track_id,
                                        art_url_ws,
                                        cached_preview,
                                        song_label,
                                        state,
                                    )
                                )
                                continue
                            if art_url_ws:
                                if art_url_ws == state.last_art_url:
                                    log(
                                        'api',
                                        '[blue]ws[/blue] [dim]· unchanged, skip[/dim]',
                                    )
                                    continue
                                song_label = f'{track_id[:8]}…'
                                state.last_track_id = track_id
                                state.last_art_url = art_url_ws
                                print(
                                    f'[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...'
                                )
                                if once:
                                    await _art_task(
                                        art_url_ws, track_id, song_label, state
                                    )
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(
                                    _art_task(art_url_ws, track_id, song_label, state)
                                )
                                continue
                            else:
                                song_label = f'{track_id[:8]}…'
                                state.last_track_id = track_id
                                print(
                                    f'[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...'
                                )
                                log(
                                    'api',
                                    f'[blue]ws[/blue] [dim]·[/dim] track [white]{track_id[:8]}…[/white] [dim]→[/dim] [yellow]fetch[/yellow]',
                                )
                                if once:
                                    await _fetch_task(track_id, song_label, state)
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(
                                    _fetch_task(track_id, song_label, state)
                                )
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
                                    and maybe.get('type') == 'ping'
                                ):
                                    await ws.send(json.dumps({'type': 'pong'}))
                                    log(
                                        'api',
                                        '[cyan]ws[/cyan] [dim]·[/dim] ping[dim]↔[/dim]pong',
                                    )
                                    continue
                            except Exception:
                                pass
                            if art_url_ws:
                                if art_url_ws == state.last_art_url:
                                    log(
                                        'api',
                                        '[blue]ws[/blue] [dim]· unchanged, skip[/dim]',
                                    )
                                    continue
                                song_label = 'Unknown track'
                                state.last_art_url = art_url_ws
                                print(
                                    f'[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...'
                                )
                                if once:
                                    await _bare_art_task(art_url_ws, song_label, state)
                                    return
                                if pending_task and not pending_task.done():
                                    pending_task.cancel()
                                pending_task = asyncio.create_task(
                                    _bare_art_task(art_url_ws, song_label, state)
                                )
                                continue
                            else:
                                log('api', '[blue]ws[/blue] [dim]· heartbeat[/dim]')
                                continue
                    art_url, title, artist = parsed
                    if not art_url:
                        log('api', '[yellow]ws[/yellow] [dim]·[/dim] no artwork, skip')
                        continue
                    if art_url == state.last_art_url:
                        log('api', '[blue]ws[/blue] [dim]· unchanged, skip[/dim]')
                        continue
                    song_label = ''
                    if title and artist:
                        song_label = f'{title} – {artist}'
                    elif title:
                        song_label = title
                    elif artist:
                        song_label = artist
                    else:
                        song_label = 'Unknown track'
                        if _pending_track_id:
                            song_label = f'{_pending_track_id[:8]}…'
                    state.last_art_url = art_url
                    if _pending_track_id:
                        state.last_track_id = _pending_track_id
                    print(
                        f'[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...'
                    )
                    if once:
                        await _parsed_task(
                            art_url, title, artist, _pending_track_id, song_label, state
                        )
                        return
                    if pending_task and not pending_task.done():
                        pending_task.cancel()
                    pending_task = asyncio.create_task(
                        _parsed_task(
                            art_url, title, artist, _pending_track_id, song_label, state
                        )
                    )

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
                'api',
                f'[yellow]ws[/yellow] [dim]·[/dim] disconnected [dim]({exc})[/dim] [dim]·[/dim] retry in [yellow]{delay:.1f}s[/yellow]',
            )
            _status = getattr(exc, 'status_code', None)
            is_auth = (
                '401' in str(exc)
                or '403' in str(exc)
                or _status in (401, 403)
                or (
                    isinstance(exc, InvalidStatusCode)
                    and getattr(exc, 'status_code', None) in (401, 403)
                )
            )
            if is_auth:  # type: ignore[attr-defined]
                print(
                    f'[yellow]Warning:[/yellow] WebSocket auth failed ({exc}) – refreshing token…'
                )
                try:
                    refreshed = _try_refresh_token(
                        config_path=getattr(globs, 'config_path', None)
                    )
                    if not refreshed:
                        refreshed = ensure_valid_token(
                            config_path=getattr(globs, 'config_path', None),
                            force_refresh=True,
                        )
                    if refreshed and refreshed != state.token:
                        state.token = refreshed
                        delay = reconnect_delay
                        log(
                            'api',
                            '[green]ws[/green] [dim]·[/dim] token refreshed, reconnecting…',
                        )
                        continue
                except Exception as refresh_exc:  # pragma: no cover
                    print(f'[bold red]Error:[/bold red] Refresh failed: {refresh_exc}')
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
                'api',
                f'[red]ws[/red] [dim]·[/dim] [red]error[/red]: {exc} [dim]·[/dim] retry in [yellow]{delay:.1f}s[/yellow]',
            )
            await asyncio.sleep(delay)
            delay = min(delay * 1.5, max_delay)
            continue
