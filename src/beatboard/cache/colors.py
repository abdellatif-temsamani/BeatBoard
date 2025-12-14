import base64
import json
import sqlite3
import zlib
from typing import List, Optional

from rich import print

from .db import get_connection
from ..globs import Globs


def compress_colors(colors: List[str]) -> str:
    raw = json.dumps(colors).encode("utf-8")
    compressed = zlib.compress(raw)
    return base64.b64encode(compressed).decode("utf-8")


def decompress_colors(data: str) -> List[str]:
    compressed = base64.b64decode(data)
    raw = zlib.decompress(compressed)
    return json.loads(raw.decode("utf-8"))


def cache_colors(name: Optional[str], colors: Optional[List[str]] = None) -> None:
    if colors is None:
        colors = []

    if not name or not name.strip():
        raise ValueError("Cache name must be provided and non-empty")

    compressed_colors = compress_colors(colors)

    if Globs().debug.get("cache"):
        print(
            f"[bold blue]CACHE WRITE[/bold blue] "
            f"{name} "
            f"[dim]({len(colors)} colors)[/dim]"
        )

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


def get_cached_colors(name: Optional[str]) -> Optional[List[str]]:
    if name is None:
        return None

    if Globs().debug.get("cache"):
        print(f"[cyan]CACHE READ[/cyan] {name}")

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
        if Globs().debug.get("cache"):
            print(
                f"[red bold]Database error while reading cached colors:[/red bold] {e}"
            )
        return None

    if row is None:
        if Globs().debug.get("cache"):
            print(f"[bold red]CACHE MISS[/bold red] {name}")
        return None

    colors = decompress_colors(row[0])

    if Globs().debug.get("cache"):
        print(
            f"[bold green]CACHE HIT[/bold green] "
            f"{name} "
            f"[dim]({len(colors)} colors)[/dim]"
        )

    return colors
