"""Main pipeline: cache lookup, download, palette, hardware, hooks."""

from __future__ import annotations

import asyncio
import time

from rich import print

from ..cache.colors import cache_colors, get_cached_colors
from ..color import debug_palette, extract_palette, get_color_palette
from ..globs import Globs
from ..plugins.hooks import run_extension_hooks
from .apply import _run_hardware
from .image import get_image
from .keys import create_cache_key, create_track_cache_key


async def process_art_url(
    art_url: str | None = None, track_id: str | None = None
) -> list[str] | None:
    """process art work of the current song

    Args:
        art_url: The new album art URL.
        track_id: Optional Spotify track id – when provided the resulting
                  palette is also indexed by track_id so the websocket
                  fast-path (``get_cached_colors_by_track_id``) can hit
                  without a second DB write.

    Returns:
        Extracted hex colors or None on failure.
    """
    IMAGE_PATH = "/tmp/album_art.jpg"
    globs = Globs()
    start_time = time.time()

    if art_url is None:
        return None

    # If we have a track_id, try indexed cache first – avoids art-hash compute + DB round-trip
    if track_id:
        from ..cache.colors import get_cached_colors_by_track_id

        hex_colors_track = get_cached_colors_by_track_id(
            create_track_cache_key(track_id)
        )
        if hex_colors_track:
            hex_colors = hex_colors_track
            from_cache = True
            # Extension hook for fast path as well
            try:
                run_extension_hooks(
                    "color_applied",
                    color=hex_colors[0] if hex_colors else "ffffff",
                    art_url=art_url or "",
                    track_id=track_id or "",
                )
            except Exception:
                pass
            # Fast path: skip download/palette, go straight to hardware
            command_start = time.time()
            await _run_hardware(hex_colors[0])
            command_time = time.time() - command_start
            if globs.debug.get("perf") or globs.debug.get("all"):
                total_ms = (time.time() - start_time) * 1000
                hw_ms = command_time * 1000
                print(
                    f"[cyan]perf[/cyan] [dim]·[/dim] total [cyan]{total_ms:.0f}ms[/cyan] [dim]·[/dim] hw [magenta]{hw_ms:.0f}ms[/magenta] [dim]track-cache[/dim]"
                )
            return hex_colors

    cache_key = create_cache_key(art_url)
    hex_colors = get_cached_colors(cache_key)
    from_cache = bool(hex_colors)

    if not hex_colors:
        # Download or fetch new album art
        try:
            await get_image(IMAGE_PATH, art_url)
        except Exception as e:
            print(f"[bold red]Error:[/bold red] fetching album art: {e}")
            return None

        # Extract the palette.
        try:
            hex_colors = await get_color_palette(IMAGE_PATH)
            # Store with both art-hash and optional track_id in one row (migration 03)
            cache_track_id = create_track_cache_key(track_id) if track_id else None
            cache_colors(cache_key, hex_colors, track_id=cache_track_id)
        except Exception as e:
            print(f"[bold red]Error:[/bold red] extracting color palette: {e}")
            return None

        if not hex_colors:
            print(
                "[bold yellow]Warning:[/bold yellow] No colors extracted from image, skipping hardware update"
            )
            return None

    # Extension hook: color_applied (before hardware, so extensions can react to color)
    try:
        run_extension_hooks(
            "color_applied",
            color=hex_colors[0] if hex_colors else "ffffff",
            art_url=art_url or "",
            track_id=track_id or "",
        )
    except Exception:
        pass

    # Hardware first – latency matters. Palette debug after.
    command_start = time.time()
    await _run_hardware(hex_colors[0])
    command_time = time.time() - command_start

    if globs.debug.get("perf") or globs.debug.get("all"):
        total_ms = (time.time() - start_time) * 1000
        hw_ms = command_time * 1000
        print(
            f"[cyan]perf[/cyan] [dim]·[/dim] total [cyan]{total_ms:.0f}ms[/cyan] [dim]·[/dim] hw [magenta]{hw_ms:.0f}ms[/magenta]"
        )

    # Palette debug after hardware so it doesn't block lighting update
    if globs.debug.get("palette") or globs.debug.get("all"):
        if from_cache and hex_colors:
            # from_cache path: need image for extracted palette debug.
            # Do it after hardware to avoid extra latency on the critical path.
            try:
                await get_image(IMAGE_PATH, art_url)
                extracted_palette = await asyncio.to_thread(extract_palette, IMAGE_PATH)
                debug_palette(hex_colors=hex_colors, palette=extracted_palette)
            except Exception as e:
                print(
                    f"[bold yellow]Warning:[/bold yellow] debug palette extraction failed: {e}"
                )

    return hex_colors
