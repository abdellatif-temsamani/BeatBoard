import asyncio
import hashlib
import os
import shutil
import subprocess
import time
from pathlib import Path

from rich import print

from .cache.colors import cache_colors, get_cached_colors
from .color_gen import (
    COLOR_CACHE_VERSION,
    debug_palette,
    extract_palette,
    get_color_palette,
)
from .globs import Globs
from .hardware import get_command
from .plugins.hooks import run_extension_hooks

# Shared HTTP session for image downloads (keep-alive saves 50-100ms per track)
_IMAGE_SESSION = None


def _get_image_session():
    global _IMAGE_SESSION
    if _IMAGE_SESSION is None:
        import requests

        s = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, pool_maxsize=10, max_retries=1
        )
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        s.headers.update({"User-Agent": "BeatBoard/0.3.0"})
        _IMAGE_SESSION = s
    return _IMAGE_SESSION


def create_cache_key(art_url: str) -> str:
    """Create a versioned cache key from an art URL.

    Args:
        art_url: The art URL to hash.

    Returns:
        A SHA256 hex digest suitable for use as a cache key.
    """
    value = f"{COLOR_CACHE_VERSION}\0{art_url}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_track_cache_key(track_id: str) -> str:
    """Namespace a Spotify track id by the active palette algorithm."""
    return f"{COLOR_CACHE_VERSION}:{track_id}"


def playerctl(*args: str) -> list[str]:
    """base playerctl command
        *args: playerctl arguments

    Returns: list[str]
    """
    return ["playerctl", "--player=spotify", *args]


def check_spotify_available() -> bool:
    """Check if Spotify player is available via playerctl.

    Returns: bool
    """
    try:
        result = subprocess.run(
            ["playerctl", "--list-all"], capture_output=True, text=True, timeout=5
        )
        return "spotify" in result.stdout
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return False


async def get_image(
    path: str,
    art_url: str | None = None,
) -> None:
    """Get the album art from the current playing song

    Args:
        path: The path to store the image temporarily
        art_url: The URL to the image. If not provided, it will be fetched from playerctl
    """

    if not art_url:
        url = await asyncio.to_thread(
            subprocess.run,
            playerctl("metadata", "mpris:artUrl"),
            capture_output=True,
            text=True,
        )

        art_url = url.stdout.strip()

    if art_url.startswith("file://"):
        """just in case the image is local"""
        file_path = art_url[7:]
        image_data = await asyncio.to_thread(Path(file_path).read_bytes)
    else:
        # Use shared session with keep-alive – saves TCP+TLS handshake per track
        def _fetch():
            sess = _get_image_session()
            resp = sess.get(art_url, timeout=5)
            resp.raise_for_status()
            return resp.content

        image_data = await asyncio.to_thread(_fetch)

    # Write file asynchronously (thread)
    await asyncio.to_thread(Path(path).write_bytes, image_data)


async def apply_colors(hex_colors: list[str]) -> None:
    """Apply given colors to hardware (no image fetch).

    Used for fast cache-hit path (e.g. track cache) to skip palette extraction.
    Hardware commands are run concurrently when multiple devices are present.
    """
    globs = Globs()
    start_hw = time.time()
    if not hex_colors:
        hex_colors = ["ffffff"]
    commands = get_command(globs.hardware, hex_colors[0])
    # Filter to available commands first
    runnable: list[list[str]] = []
    for command in commands:
        if not (shutil.which(command[0]) or os.path.exists(command[0])):
            print(
                f"[bold red]Error:[/bold red] Command [bold]'{command[0]}'[/bold] not found. Skipping hardware command."
            )
            continue
        if globs.debug.get("command") or globs.debug.get("all"):
            cmd_str = " ".join(command)
            print(f"[magenta]hw[/magenta] [dim]·[/dim] {cmd_str}")
        runnable.append(command)

    if runnable:
        # Run concurrently – saves ~200ms when multiple hardware present, and keeps
        # single-device case identical (one task).
        async def _run(cmd: list[str]):
            try:
                await asyncio.to_thread(subprocess.run, cmd)
            except Exception as e:
                print(f"[bold red]Error:[/bold red] running hardware command: {e}")

        if len(runnable) == 1:
            await _run(runnable[0])
        else:
            await asyncio.gather(*(_run(c) for c in runnable))
    if globs.debug.get("perf") or globs.debug.get("all"):
        hw_ms = (time.time() - start_hw) * 1000
        print(f"[cyan]perf[/cyan] [dim]·[/dim] hw [cyan]{hw_ms:.0f}ms[/cyan]")


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
        from .cache.colors import get_cached_colors_by_track_id

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
            commands = get_command(globs.hardware, hex_colors[0])
            # concurrent hardware
            runnable = []
            for command in commands:
                if not (shutil.which(command[0]) or os.path.exists(command[0])):
                    print(
                        f"[bold red]Error:[/bold red] Command [bold]'{command[0]}'[/bold] not found. Skipping hardware command."
                    )
                    continue
                if globs.debug.get("command") or globs.debug.get("all"):
                    cmd_str = " ".join(command)
                    print(f"[magenta]hw[/magenta] [dim]·[/dim] {cmd_str}")
                runnable.append(command)
            if runnable:
                if len(runnable) == 1:
                    try:
                        await asyncio.to_thread(subprocess.run, runnable[0])
                    except Exception as e:
                        print(
                            f"[bold red]Error:[/bold red] running hardware command: {e}"
                        )
                else:

                    async def _run(cmd: list[str]):
                        try:
                            await asyncio.to_thread(subprocess.run, cmd)
                        except Exception as e:
                            print(
                                f"[bold red]Error:[/bold red] running hardware command: {e}"
                            )

                    await asyncio.gather(*(_run(c) for c in runnable))
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
                "[bold yellow]Warning:[/bold yellow] No colors extracted from image, using fallback"
            )
            hex_colors = ["ffffff"]  # fallback color

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
    commands = get_command(globs.hardware, hex_colors[0])
    runnable2: list[list[str]] = []
    for command in commands:
        if not (shutil.which(command[0]) or os.path.exists(command[0])):
            print(
                f"[bold red]Error:[/bold red] Command [bold]'{command[0]}'[/bold] not found. Skipping hardware command."
            )
            continue
        if globs.debug.get("command") or globs.debug.get("all"):
            cmd_str = " ".join(command)
            print(f"[magenta]hw[/magenta] [dim]·[/dim] {cmd_str}")
        runnable2.append(command)
    if runnable2:
        if len(runnable2) == 1:
            try:
                await asyncio.to_thread(subprocess.run, runnable2[0])
            except Exception as e:
                print(f"[bold red]Error:[/bold red] running hardware command: {e}")
        else:

            async def _run2(cmd: list[str]):
                try:
                    await asyncio.to_thread(subprocess.run, cmd)
                except Exception as e:
                    print(f"[bold red]Error:[/bold red] running hardware command: {e}")

            await asyncio.gather(*(_run2(c) for c in runnable2))
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


async def watch_playerctl(once: bool = False):
    """Stream metadata changes from playerctl --follow.
    We grab both artUrl and title/artist.

    Args:
        follow: Whether to follow the playerctl output. If False, only the current state is returned.
    """
    process = await asyncio.create_subprocess_exec(
        *playerctl(
            "metadata",
            "--format",
            "{{mpris:artUrl}}|{{xesam:title}}|{{xesam:artist}}",
            "--follow",
        ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert process.stdout is not None

    async for raw_line in process.stdout:
        decoded = raw_line.decode().strip()

        if not decoded or "|" not in decoded:
            continue

        art_url, title, artist = decoded.split("|", 2)

        if not art_url:
            continue  # no image? skip event

        song_label = f"{title} – {artist}" if artist else title

        # Extension hook: track_change
        try:
            run_extension_hooks(
                "track_change", title=title, artist=artist, art_url=art_url
            )
        except Exception:
            pass

        print(
            f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
        )

        await process_art_url(art_url, track_id=None)
        # Extension hook: track processing done, color will be handled in process_art_url
        # color_applied is triggered inside process_art_url after palette extraction

        print("[bold green]Processing done[/bold green].")
        print("[dim]" + "─" * 50 + "[/dim]")
        print("")

        if once:
            break
