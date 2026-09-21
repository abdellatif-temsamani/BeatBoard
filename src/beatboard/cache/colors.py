import base64
import json
import re
import sqlite3
import time
import zlib
from typing import Dict, List, Optional

from rich import print

from ..globs import Globs
from ..logs import log
from .db import get_connection

# ---------------------------------------------------------------------------
# In-memory LRU caches for hot path – avoids 1ms SQLite round-trip on WS
# ---------------------------------------------------------------------------
_MAX_MEM = 512
_mem_by_name: Dict[str, List[str]] = {}
_mem_by_track: Dict[str, List[str]] = {}
_mem_order: List[str] = []  # simple LRU order (keys = f"n:{name}" / f"t:{tid}")


def _mem_get_name(name: str) -> Optional[List[str]]:
    return _mem_by_name.get(name)


def _mem_get_track(track_id: str) -> Optional[List[str]]:
    return _mem_by_track.get(track_id)


def _mem_put(
    name: Optional[str], colors: List[str], track_id: Optional[str] = None
) -> None:
    # keep order bounded
    if name:
        _mem_by_name[name] = colors
        _mem_order.append(f"n:{name}")
    if track_id:
        _mem_by_track[track_id] = colors
        _mem_order.append(f"t:{track_id}")
        # also populate track_ prefixed name for legacy callers
        legacy = f"track_{track_id}"
        _mem_by_name[legacy] = colors
    # evict if needed (very cheap – not strict LRU but bounded)
    while len(_mem_order) > _MAX_MEM * 2:
        oldest = _mem_order.pop(0)
        if oldest.startswith("n:"):
            k = oldest[2:]
            _mem_by_name.pop(k, None)
        else:
            k = oldest[2:]
            _mem_by_track.pop(k, None)


def _has_track_id_column(conn: sqlite3.Connection) -> bool:
    """Check if colors_cache has track_id column (migration 03)."""
    try:
        cur = conn.execute("PRAGMA table_info(colors_cache)")
        cols = [row[1] for row in cur.fetchall()]
        return "track_id" in cols
    except sqlite3.Error:
        return False


def compress_colors(colors: List[str]) -> str:
    """Compress a list of color strings into a base64-encoded string.

    Args:
        colors: List of color strings to compress.

    Returns:
        Base64-encoded compressed string.
    """
    raw = json.dumps(colors).encode("utf-8")
    compressed = zlib.compress(raw)
    return base64.b64encode(compressed).decode("utf-8")


def decompress_colors(data: str) -> List[str]:
    """Decompress a base64-encoded string back into a list of color strings.

    Args:
        data: Base64-encoded compressed string.

    Returns:
        List of decompressed color strings.
    """
    compressed = base64.b64decode(data)
    raw = zlib.decompress(compressed)
    return json.loads(raw.decode("utf-8"))


def cache_colors(
    name: Optional[str],
    colors: Optional[List[str]] = None,
    track_id: Optional[str] = None,
) -> None:
    """Cache a list of colors in the database under the given name.

    Args:
        name: The cache name. Must be non-empty and contain only alphanumeric, underscore, or hyphen.
              For art-url cache this is the sha256 hex (64 chars).
        colors: List of color strings to cache. Defaults to empty list.
        track_id: Optional Spotify track id (22-char). When provided and the
                  ``track_id`` column exists, the row is indexed by both
                  ``name`` and ``track_id`` so websocket fast-path can hit
                  via track_id without a second row.

    Raises:
        ValueError: If name is invalid.
        sqlite3.Error: If database operation fails.
    """
    globs = Globs()
    start_time = time.time()

    if colors is None:
        colors = []

    if not name or not name.strip():
        raise ValueError("Cache name must be provided and non-empty")

    # Validate cache name format
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        raise ValueError(
            "Cache name must contain only alphanumeric characters, underscores, and hyphens"
        )

    # Derive track_id from legacy track_ name if not explicitly given
    derived_track: Optional[str] = track_id
    if derived_track is None and name.startswith("track_"):
        cand = name[6:].strip()
        if cand:
            derived_track = cand

    # Normalize track_id
    if derived_track is not None:
        derived_track = derived_track.strip() or None

    compressed_colors = compress_colors(colors)

    with get_connection() as db:
        try:
            cursor = db.cursor()
            has_col = _has_track_id_column(db)
            if has_col and derived_track:
                # Upsert by name, also store track_id for indexed lookup.
                # Keep legacy row for name=track_... for backward compat, but
                # also ensure art-hash row carries track_id.
                # If name is track_..., we store with that name + track_id.
                # If name is art hash, we store art hash + track_id.
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
                # For art-hash case, also ensure a track_ alias row exists only for
                # legacy readers that still query by name=track_... (optional, but
                # keeps get_cached_colors("track_...") working even if track_id col missing).
                # We maintain a second lightweight row only if name is not track_...:
                # Instead of duplicate, we rely on track_id index for fast path, so we
                # don't create a second row. Legacy fallback in get_cached_colors will
                # query track_id column first, so no need for duplicate.
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
                # If we have track_id but column missing (old DB / in-memory test DB),
                # also store a legacy track_ alias row? Not needed – fallback path will
                # query legacy name directly.
                if derived_track and not has_col:
                    # Ensure legacy alias still works via name lookup – already is name=track_...
                    pass

            db.commit()
        except sqlite3.Error as e:
            print(f"[red bold]Database error while caching colors:[/red bold] {e}")
            raise
    # Populate in-memory caches
    _mem_put(name, colors, derived_track)
    total_ms = (time.time() - start_time) * 1000
    short = name[:8] + "…" if len(name) > 8 else name
    msg = f"[cyan]cache[/cyan] [dim]·[/dim] write [white]{short}[/white] [dim]({len(colors)} colors)[/dim] [dim]·[/dim] [cyan]{total_ms:.0f}ms[/cyan]"
    if globs.debug.get("cache") or globs.debug.get("perf") or globs.debug.get("all"):
        print(msg)


def cache_colors_by_track_id(track_id: str, colors: List[str]) -> None:
    """Convenience: cache colors indexed by Spotify track_id.

    Stores a row with ``name = track_<id>`` for legacy compatibility and
    also populates the ``track_id`` column when available so
    :func:`get_cached_colors_by_track_id` can hit the index.

    Args:
        track_id: Spotify track id (22 chars).
        colors: List of hex colors without ``#``.
    """
    if not track_id or not track_id.strip():
        raise ValueError("track_id must be provided and non-empty")
    track_id = track_id.strip()
    # Legacy name for backward compat
    name = f"track_{track_id}"
    cache_colors(name, colors, track_id=track_id)


def get_cached_colors_by_track_id(track_id: Optional[str]) -> Optional[List[str]]:
    """Retrieve cached colors by Spotify track_id using indexed column.

    Fast path for websocket: avoids an API fetch and palette extraction
    when the track has been seen before.

    Args:
        track_id: Spotify track id.

    Returns:
        List of color strings if found, None otherwise.
    """
    globs = Globs()
    start_time = time.time()

    if track_id is None:
        return None
    track_id = track_id.strip()
    if not track_id:
        return None

    # Memory fast path
    mem = _mem_get_track(track_id)
    if mem is not None:
        # also count as hit for logging parity
        if (
            globs.debug.get("cache")
            or globs.debug.get("perf")
            or globs.debug.get("all")
        ):
            total_ms = (time.time() - start_time) * 1000
            short = f"track_{track_id[:8]}…"
            print(
                f"[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] [dim]({len(mem)} colors)[/dim] [dim]·[/dim] [green]{total_ms:.0f}ms[/green] [dim]mem[/dim]"
            )
        return mem

    short = f"track_{track_id[:8]}…"
    # Try DB indexed column first, fallback to legacy name
    try:
        with get_connection() as db:
            has_col = _has_track_id_column(db)
            row = None
            if has_col:
                # Indexed lookup – primary fast path
                cur = db.execute(
                    "SELECT colors FROM colors_cache WHERE track_id = ? LIMIT 1",
                    (track_id,),
                )
                row = cur.fetchone()
                # Fallback to legacy name if not found (handles DBs migrated partially)
                if row is None:
                    cur = db.execute(
                        "SELECT colors FROM colors_cache WHERE name = ?",
                        (f"track_{track_id}",),
                    )
                    row = cur.fetchone()
            else:
                # Old DB / in-memory test DB without column – legacy path
                cur = db.execute(
                    "SELECT colors FROM colors_cache WHERE name = ?",
                    (f"track_{track_id}",),
                )
                row = cur.fetchone()

            if row is None:
                total_ms = (time.time() - start_time) * 1000
                msg = f"[yellow]cache[/yellow] [dim]·[/dim] miss [white]{short}[/white] [dim]·[/dim] [yellow]{total_ms:.0f}ms[/yellow]"
                if (
                    globs.debug.get("cache")
                    or globs.debug.get("perf")
                    or globs.debug.get("all")
                ):
                    print(msg)
                return None

            try:
                colors = decompress_colors(row[0])
            except (ValueError, zlib.error, json.JSONDecodeError):
                log("cache", f"[red bold]cache · corrupt[/red bold] {short}")
                return None

            # populate memory
            _mem_put(f"track_{track_id}", colors, track_id)

            total_ms = (time.time() - start_time) * 1000
            msg = f"[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] [dim]({len(colors)} colors)[/dim] [dim]·[/dim] [green]{total_ms:.0f}ms[/green]"
            if (
                globs.debug.get("cache")
                or globs.debug.get("perf")
                or globs.debug.get("all")
            ):
                print(msg)
            return colors
    except sqlite3.Error as e:
        log("cache", f"[red bold]cache · error[/red bold] {short} {e}")
        return None


def get_cached_colors(name: Optional[str]) -> Optional[List[str]]:
    """Retrieve cached colors from the database by name.

    Args:
        name: The cache name to retrieve. Supports legacy ``track_<id>`` names
              by delegating to :func:`get_cached_colors_by_track_id` when the
              indexed column exists.

    Returns:
        List of color strings if found and valid, None otherwise.
    """
    globs = Globs()
    start_time = time.time()

    if name is None:
        return None

    # If legacy track_ name, try indexed track_id fast path first
    if name.startswith("track_"):
        track_id = name[6:]
        # try indexed lookup – will hit memory or indexed column
        res = get_cached_colors_by_track_id(track_id)
        if res is not None:
            return res
        # fallback continues to legacy name lookup below if indexed miss
        # (but get_cached_colors_by_track_id already tried legacy name, so we will just return None)
        # To avoid double miss logging, return None directly if we already did indexed lookup
        # However keep legacy path for DBs without column – already handled in helper.
        return None

    # Memory fast path for art-hash names
    mem = _mem_get_name(name)
    if mem is not None:
        if (
            globs.debug.get("cache")
            or globs.debug.get("perf")
            or globs.debug.get("all")
        ):
            total_ms = (time.time() - start_time) * 1000
            short = name[:8] + "…" if len(name) > 8 else name
            print(
                f"[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] [dim]({len(mem)} colors)[/dim] [dim]·[/dim] [green]{total_ms:.0f}ms[/green] [dim]mem[/dim]"
            )
        return mem

    short = name[:8] + "…" if len(name) > 8 else name
    try:
        with get_connection() as db:
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
            "cache",
            f"[red bold]cache · error[/red bold] {short} {e}",
        )
        return None

    if row is None:
        total_ms = (time.time() - start_time) * 1000
        msg = f"[yellow]cache[/yellow] [dim]·[/dim] miss [white]{short}[/white] [dim]·[/dim] [yellow]{total_ms:.0f}ms[/yellow]"
        if (
            globs.debug.get("cache")
            or globs.debug.get("perf")
            or globs.debug.get("all")
        ):
            print(msg)
        return None

    try:
        colors = decompress_colors(row[0])
    except (ValueError, zlib.error, json.JSONDecodeError):
        log("cache", f"[red bold]cache · corrupt[/red bold] {short}")
        return None

    _mem_put(name, colors)
    total_ms = (time.time() - start_time) * 1000
    msg = f"[green]cache[/green] [dim]·[/dim] hit [white]{short}[/white] [dim]({len(colors)} colors)[/dim] [dim]·[/dim] [green]{total_ms:.0f}ms[/green]"
    if globs.debug.get("cache") or globs.debug.get("perf") or globs.debug.get("all"):
        print(msg)

    return colors


def clear_memory_cache() -> None:
    """Clear in-memory caches (useful for tests)."""
    _mem_by_name.clear()
    _mem_by_track.clear()
    _mem_order.clear()
