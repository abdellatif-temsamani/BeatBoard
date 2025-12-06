import asyncio
import subprocess
from pathlib import Path
from typing import Awaitable, Callable


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
            ["playerctl", "--player=spotify", "metadata", "mpris:artUrl"],
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


async def watch_playerctl(handle_art_change: Callable[[str], Awaitable[None]]):
    """ Stream metadata changes from playerctl --follow.
    We grab both artUrl and title/artist.

    Args:
        handle_art_change: A callback to handle the art change. runs on every song change.
    """
    process = await asyncio.create_subprocess_exec(
        "playerctl",
        "metadata",
        "--format",
        "{{mpris:artUrl}}|{{xesam:title}}|{{xesam:artist}}",
        "--follow",
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

        print(f'Processing "{song_label}"...')

        await handle_art_change(art_url)

        print("Processing done.")
