import asyncio
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from rich import print

from .cache.colors import cache_colors, get_cached_colors
from .color_gen import get_color_palette
from .globs import Globs
from .hardware import get_command


def create_cache_key(art_url: str) -> str:
    """Create a sanitized cache key from an art URL.

    Args:
        art_url: The art URL to hash.

    Returns:
        A SHA256 hex digest suitable for use as a cache key.
    """
    return hashlib.sha256(art_url.encode("utf-8")).hexdigest()


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

    import requests

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
        # requests.get is blocking → run it in a thread
        response = await asyncio.to_thread(requests.get, art_url)
        response.raise_for_status()
        image_data = response.content

    # Write file asynchronously (thread)
    await asyncio.to_thread(Path(path).write_bytes, image_data)


async def process_art_url(art_url: str | None = None) -> None:
    """process art work of the current song

    Args:
        art_url: The new album art URL.
    """
    IMAGE_PATH = "/tmp/album_art.jpg"

    if art_url is None:
        return

    cache_key = create_cache_key(art_url)
    hex_colors = get_cached_colors(cache_key)

    if not hex_colors:
        # Download or fetch new album art
        try:
            await get_image(IMAGE_PATH, art_url)
        except Exception as e:
            print(f"[bold red]Error:[/bold red] fetching album art: {e}")
            return

        # Extract palette (CPU-bound, run in thread)
        try:
            hex_colors = await get_color_palette(IMAGE_PATH)
            cache_colors(cache_key, hex_colors)
        except Exception as e:
            print(f"[bold red]Error:[/bold red] extracting color palette: {e}")
            return

        if not hex_colors:
            print(
                "[bold yellow]Warning:[/bold yellow] No colors extracted from image, using fallback"
            )
            hex_colors = ["ffffff"]  # fallback color

    globs = Globs()
    commands = get_command(globs.hardware, hex_colors[0])

    for command in commands:
        # Check if the command executable exists
        if not (shutil.which(command[0]) or os.path.exists(command[0])):
            print(
                f"[bold red]Error:[/bold red] Command [bold]'{command[0]}'[/bold] not found. Skipping hardware command."
            )
            continue
        if globs.debug["command"]:
            print(f"Running command: {command}")
        try:
            await asyncio.to_thread(subprocess.run, command)
        except Exception as e:
            print(f"[bold red]Error:[/bold red] running hardware command: {e}")


async def watch_playerctl(follow: bool = True):
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

        print(f'[bold yellow]Processing[/bold yellow] "{song_label}"...')

        await process_art_url(art_url)

        print("[bold green]Processing done[/bold green].")
        print("")

        if not follow:
            break
