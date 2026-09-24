"""Persistent cache store – DB read/write for palettes."""

from __future__ import annotations

import json
import re
import sqlite3
import time
import zlib
from typing import List, Optional

from rich import print

from ..globs import Globs
from ..logs import log
from .compression import compress_colors, decompress_colors
from .db import _has_track_id_column
from .memory import _mem_get_name, _mem_get_track, _mem_put


def _get_conn():
    # Dynamic lookup so ``patch('beatboard.cache.colors.get_connection')`` affects
    # store as well – tests patch the facade, not db directly.
    try:
        import beatboard.cache.colors as _colors

        # Use facade's get_connection if it exists and is patched
        gc = getattr(_colors, 'get_connection', None)
        if gc is not None:
            return gc()
    except Exception:
        pass
    from .db import get_connection as _gc

    return _gc()


def cache_colors(
    name: Optional[str],
    colors: Optional[List[str]] = None,
    track_id: Optional[str] = None,
) -> None:
    """Cache a list of colors in the database under the given name."""
    globs = Globs()
    start_time = time.time()

    if colors is None:
        colors = []

    if not name or not name.strip():
        raise ValueError('Cache name must be provided and non-empty')

    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValueError(
            'Cache name must contain only alphanumeric characters, '
            'underscores, and hyphens'
        )

    derived_track: Optional[str] = track_id
    if derived_track is None and name.startswith('track_'):
        cand = name[6:].strip()
        if cand:
            derived_track = cand

    if derived_track is not None:
        derived_track = derived_track.strip() or None

    compressed_colors = compress_colors(colors)

    with _get_conn() as db:
        try:
            cursor = db.cursor()
            has_col = _has_track_id_column(db)
            if has_col and derived_track:
                cursor.execute(
                    """
                    INSERT INTO colors_cache (name, colors, track_id)
                    VALUES (?, ?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                      colors = excluded.colors,
                      track_id = COALESCE(excluded.track_id, colors_cache.track_id)
                    """,
                    (name, compressed_colors, derived_track),
                )
            else:
                cursor.execute(
                    """
                    INSERT INTO colors_cache (name, colors)
                    VALUES (?, ?)
                    ON CONFLICT(name) DO UPDATE SET
                      colors = excluded.colors
                    """,
                    (name, compressed_colors),
                )

            db.commit()
        except sqlite3.Error as e:
            print(f'[red bold]Database error while caching colors:[/red bold] {e}')
            raise
    _mem_put(name, colors, derived_track)
    total_ms = (time.time() - start_time) * 1000
    short = name[:8] + '…' if len(name) > 8 else name
    msg = (
        f'[cyan]cache[/cyan] [dim]·[/dim] write [white]{short}[/white] '
        f'[dim]({len(colors)} colors)[/dim] [dim]·[/dim] [cyan]{total_ms:.0f}ms[/cyan]'
    )
    if globs.debug.get('cache') or globs.debug.get('perf') or globs.debug.get('all'):
        print(msg)


def cache_colors_by_track_id(track_id: str, colors: List[str]) -> None:
    """Convenience: cache colors indexed by Spotify track_id."""
    if not track_id or not track_id.strip():
        raise ValueError('track_id must be provided and non-empty')
    track_id = track_id.strip()
    name = f'track_{track_id}'
    cache_colors(name, colors, track_id=track_id)


def get_cached_colors_by_track_id(track_id: Optional[str]) -> Optional[List[str]]:
    """Retrieve cached colors by Spotify track_id using indexed column."""
    globs = Globs()
    start_time = time.time()

    if track_id is None:
        return None
    track_id = track_id.strip()
    if not track_id:
        return None

    mem = _mem_get_track(track_id)
    if mem is not None:
        if (
            globs.debug.get('cache')
            or globs.debug.get('perf')
            or globs.debug.get('all')
        ):
            total_ms = (time.time() - start_time) * 1000
            short = f'track_{track_id[:8]}…'
            print(
                f'[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] '
                f'[dim]({len(mem)} colors)[/dim] [dim]·[/dim] '
                f'[green]{total_ms:.0f}ms[/green] [dim]mem[/dim]'
            )
        return mem

    short = f'track_{track_id[:8]}…'
    try:
        with _get_conn() as db:
            has_col = _has_track_id_column(db)
            row = None
            if has_col:
                cur = db.execute(
                    'SELECT colors FROM colors_cache WHERE track_id = ? LIMIT 1',
                    (track_id,),
                )
                row = cur.fetchone()
                if row is None:
                    cur = db.execute(
                        'SELECT colors FROM colors_cache WHERE name = ?',
                        (f'track_{track_id}',),
                    )
                    row = cur.fetchone()
            else:
                cur = db.execute(
                    'SELECT colors FROM colors_cache WHERE name = ?',
                    (f'track_{track_id}',),
                )
                row = cur.fetchone()

            if row is None:
                total_ms = (time.time() - start_time) * 1000
                msg = (
                    f'[yellow]cache[/yellow] [dim]·[/dim] miss [white]{short}[/white] '
                    f'[dim]·[/dim] [yellow]{total_ms:.0f}ms[/yellow]'
                )
                if (
                    globs.debug.get('cache')
                    or globs.debug.get('perf')
                    or globs.debug.get('all')
                ):
                    print(msg)
                return None

            try:
                colors = decompress_colors(row[0])
            except (ValueError, zlib.error, json.JSONDecodeError):
                log('cache', f'[red bold]cache · corrupt[/red bold] {short}')
                return None

            _mem_put(f'track_{track_id}', colors, track_id)

            total_ms = (time.time() - start_time) * 1000
            msg = (
                f'[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] '
                f'[dim]({len(colors)} colors)[/dim] [dim]·[/dim] '
                f'[green]{total_ms:.0f}ms[/green]'
            )
            if (
                globs.debug.get('cache')
                or globs.debug.get('perf')
                or globs.debug.get('all')
            ):
                print(msg)
            return colors
    except sqlite3.Error as e:
        log('cache', f'[red bold]cache · error[/red bold] {short} {e}')
        return None


def get_cached_colors(name: Optional[str]) -> Optional[List[str]]:
    """Retrieve cached colors from the database by name."""
    globs = Globs()
    start_time = time.time()

    if name is None:
        return None

    if name.startswith('track_'):
        track_id = name[6:]
        res = get_cached_colors_by_track_id(track_id)
        if res is not None:
            return res
        return None

    mem = _mem_get_name(name)
    if mem is not None:
        if (
            globs.debug.get('cache')
            or globs.debug.get('perf')
            or globs.debug.get('all')
        ):
            total_ms = (time.time() - start_time) * 1000
            short = name[:8] + '…' if len(name) > 8 else name
            print(
                f'[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] '
                f'[dim]({len(mem)} colors)[/dim] [dim]·[/dim] '
                f'[green]{total_ms:.0f}ms[/green] [dim]mem[/dim]'
            )
        return mem

    short = name[:8] + '…' if len(name) > 8 else name
    try:
        with _get_conn() as db:
            cursor = db.execute(
                """
                SELECT colors
                FROM colors_cache
                WHERE name = ?
                """,
                (name,),
            )
            row = cursor.fetchone()
    except sqlite3.Error as e:
        log(
            'cache',
            f'[red bold]cache · error[/red bold] {short} {e}',
        )
        return None

    if row is None:
        total_ms = (time.time() - start_time) * 1000
        msg = (
            f'[yellow]cache[/yellow] [dim]·[/dim] miss [white]{short}[/white] '
            f'[dim]·[/dim] [yellow]{total_ms:.0f}ms[/yellow]'
        )
        if (
            globs.debug.get('cache')
            or globs.debug.get('perf')
            or globs.debug.get('all')
        ):
            print(msg)
        return None

    try:
        colors = decompress_colors(row[0])
    except (ValueError, zlib.error, json.JSONDecodeError):
        log('cache', f'[red bold]cache · corrupt[/red bold] {short}')
        return None

    _mem_put(name, colors)
    total_ms = (time.time() - start_time) * 1000
    msg = (
        f'[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] '
        f'[dim]({len(colors)} colors)[/dim] [dim]·[/dim] '
        f'[green]{total_ms:.0f}ms[/green]'
    )
    if globs.debug.get('cache') or globs.debug.get('perf') or globs.debug.get('all'):
        print(msg)

    return colors
