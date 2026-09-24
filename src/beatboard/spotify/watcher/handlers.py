"""Message handlers – task factories for Dealer push branches."""

from __future__ import annotations

import asyncio
import time

from rich import print

from ...logs import log


async def _process_resolved_art(
    art_url: str,
    title: str | None,
    artist: str | None,
    track_id: str | None,
    song_label: str,
    state,
) -> None:
    """Process resolved artwork via playerctl pipeline."""
    try:
        from ...plugins.hooks import run_extension_hooks

        run_extension_hooks(
            'track_change',
            title=title or '',
            artist=artist or '',
            art_url=art_url or '',
            track_id=track_id or '',
        )
    except Exception:
        pass
    proc_t0 = time.perf_counter()
    try:
        from ...playerctl import process_art_url

        await process_art_url(art_url, track_id=track_id)
    except asyncio.CancelledError:
        log(
            'api',
            f'[yellow]ws[/yellow] [dim]·[/dim] cancelled [white]{song_label}[/white]',
        )
        raise
    except Exception as exc:
        log(
            'api',
            f'[red]ws[/red] [dim]·[/dim] process failed [white]{song_label}[/white] [red]{exc}[/red]',
        )
        return
    proc_dt = (time.perf_counter() - proc_t0) * 1000
    log(
        'api',
        f'[blue]ws[/blue] [dim]·[/dim] [green]{song_label}[/green] [dim]·[/dim] [cyan]{proc_dt:.0f}ms[/cyan]',
    )
    state.last_art_url = art_url
    if track_id:
        state.last_track_id = track_id


async def _cache_hit_task(
    track_id: str,
    art_url_ws: str | None,
    cached_preview,
    song_label: str,
    state,
) -> None:
    """Handle cache-hit path – apply cached colors directly."""
    try:
        try:
            from ...plugins.hooks import run_extension_hooks as _reh

            _reh(
                'track_change',
                title='',
                artist='',
                art_url=art_url_ws or '',
                track_id=track_id or '',
            )
        except Exception:
            pass
        proc_t0 = time.perf_counter()
        from ...playerctl import apply_colors as _apply_colors

        await _apply_colors(cached_preview)
        try:
            from ...plugins.hooks import run_extension_hooks as _reh2

            _reh2(
                'color_applied',
                color=cached_preview[0] if cached_preview else 'ffffff',
                art_url=art_url_ws or '',
                track_id=track_id or '',
            )
        except Exception:
            pass
        proc_dt = (time.perf_counter() - proc_t0) * 1000
        log(
            'api',
            f'[blue]ws[/blue] [dim]·[/dim] [green]{song_label}[/green] [dim]·[/dim] [cyan]{proc_dt:.0f}ms[/cyan]',
        )
        print('[bold green]Processing done[/bold green].')
        print('[dim]' + '─' * 50 + '[/dim]')
        print('')
        state.last_track_id = track_id
        state.last_art_url = art_url_ws or f'track_{track_id}'
    except asyncio.CancelledError:
        log(
            'api',
            f'[yellow]ws[/yellow] [dim]·[/dim] cancelled [white]{song_label}[/white]',
        )
        raise
    except Exception as exc:
        log(
            'api',
            f'[red]ws[/red] [dim]·[/dim] cache apply failed [red]{exc}[/red]',
        )


async def _art_task(
    art_url_ws: str,
    track_id: str,
    song_label: str,
    state,
) -> None:
    """Handle track_id with inline artwork."""
    try:
        await _process_resolved_art(art_url_ws, None, None, track_id, song_label, state)
        print('[bold green]Processing done[/bold green].')
        print('[dim]' + '─' * 50 + '[/dim]')
        print('')
    except asyncio.CancelledError:
        raise


async def _fetch_task(
    track_id: str,
    song_label: str,
    state,
) -> None:
    """Fetch track via REST when Dealer payload lacks artwork."""
    try:
        from ..api import _fetch_track_sync

        fetched = await asyncio.to_thread(_fetch_track_sync, track_id, state.token)
    except Exception as exc:
        log(
            'api',
            f'[red]ws[/red] [dim]·[/dim] fetch failed: [red]{exc}[/red]',
        )
        try:
            print('[bold green]Processing done[/bold green].')
            print('[dim]' + '─' * 50 + '[/dim]')
            print('')
        except Exception:
            pass
        return
    art_fetched, title_fetched, artist_fetched = fetched
    if art_fetched is None and title_fetched is None:
        try:
            from ..auth import _try_refresh_token

            refreshed = _try_refresh_token(
                config_path=getattr(state.globs, 'config_path', None)
            )
            if refreshed and refreshed != state.token:
                state.token = refreshed
                from ..api import _fetch_track_sync as _fts2

                fetched = await asyncio.to_thread(_fts2, track_id, state.token)
                art_fetched, title_fetched, artist_fetched = fetched
        except Exception:
            pass
    if not art_fetched:
        log('api', '[yellow]ws[/yellow] [dim]·[/dim] no artwork, skip')
        try:
            print('[bold green]Processing done[/bold green].')
            print('[dim]' + '─' * 50 + '[/dim]')
            print('')
        except Exception:
            pass
        return
    better_label = song_label
    if title_fetched and artist_fetched:
        better_label = f'{title_fetched} – {artist_fetched}'
    elif title_fetched:
        better_label = title_fetched
    await _process_resolved_art(
        art_fetched, title_fetched, artist_fetched, track_id, better_label, state
    )
    try:
        print('[bold green]Processing done[/bold green].')
        print('[dim]' + '─' * 50 + '[/dim]')
        print('')
    except Exception:
        pass


async def _bare_art_task(
    art_url_ws: str,
    song_label: str,
    state,
) -> None:
    """Handle bare artwork without track_id."""
    try:
        await _process_resolved_art(art_url_ws, None, None, None, song_label, state)
        print('[bold green]Processing done[/bold green].')
        print('[dim]' + '─' * 50 + '[/dim]')
        print('')
    except asyncio.CancelledError:
        raise


async def _parsed_task(
    art_url: str,
    title: str | None,
    artist: str | None,
    track_id: str | None,
    song_label: str,
    state,
) -> None:
    """Handle parsed (art_url, title, artist) push."""
    try:
        await _process_resolved_art(art_url, title, artist, track_id, song_label, state)
        print('[bold green]Processing done[/bold green].')
        print('[dim]' + '─' * 50 + '[/dim]')
        print('')
    except asyncio.CancelledError:
        raise


__all__ = [
    '_process_resolved_art',
    '_cache_hit_task',
    '_art_task',
    '_fetch_task',
    '_bare_art_task',
    '_parsed_task',
]
