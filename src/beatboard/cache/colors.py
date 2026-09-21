import base64
import json
import re
import sqlite3
import time
import zlib
from typing import List, Optional

from rich import print

from ..globs import Globs
from ..logs import log
from .db import get_connection


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


def cache_colors(name: Optional[str], colors: Optional[List[str]] = None) -> None:
    """Cache a list of colors in the database under the given name.

    Args:
        name: The cache name. Must be non-empty and contain only alphanumeric, underscore, or hyphen.
        colors: List of color strings to cache. Defaults to empty list.

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

    compressed_colors = compress_colors(colors)

    with get_connection() as db:
        try:
            cursor = db.cursor()
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
            print(f"[red bold]Database error while caching colors:[/red bold] {e}")
            raise
    total_ms = (time.time() - start_time) * 1000
    short = name[:8] + "…" if len(name) > 8 else name
    log("cache", f"[dim]cache[/dim] · write {short} [dim]({len(colors)} colors)[/dim] · {total_ms:.0f}ms")
    if globs.debug.get("perf") or globs.debug.get("all"):
        print(f"[dim]cache[/dim] · write {short} [dim]({len(colors)} colors)[/dim] · {total_ms:.0f}ms")


def get_cached_colors(name: Optional[str]) -> Optional[List[str]]:
    """Retrieve cached colors from the database by name.

    Args:
        name: The cache name to retrieve.

    Returns:
        List of color strings if found and valid, None otherwise.
    """
    globs = Globs()
    start_time = time.time()

    if name is None:
        return None

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
        msg = f"[dim]cache[/dim] · miss {short} · {total_ms:.0f}ms"
        log("cache", msg)
        if globs.debug.get("perf") or globs.debug.get("all"):
            print(msg)
        return None

    try:
        colors = decompress_colors(row[0])
    except (ValueError, zlib.error, json.JSONDecodeError):
        log("cache", f"[red bold]cache · corrupt[/red bold] {short}")
        return None

    total_ms = (time.time() - start_time) * 1000
    msg = f"[dim]cache[/dim] · hit {short} [dim]({len(colors)} colors)[/dim] · {total_ms:.0f}ms"
    log("cache", msg)
    if globs.debug.get("perf") or globs.debug.get("all"):
        print(msg)

    return colors
