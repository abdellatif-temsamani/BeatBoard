"""Async watcher streaming playerctl --follow."""

from __future__ import annotations

import asyncio

from rich import print

from ..plugins.hooks import run_extension_hooks
from .player import playerctl
from .process import process_art_url


async def watch_playerctl(once: bool = False):
    """Stream metadata changes from playerctl --follow.
    We grab both artUrl and title/artist.

    Args:
        follow: Whether to follow the playerctl output. If False, only the current state is returned.
    """
    process = await asyncio.create_subprocess_exec(
        *playerctl(
            'metadata',
            '--format',
            '{{mpris:artUrl}}|{{xesam:title}}|{{xesam:artist}}',
            '--follow',
        ),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert process.stdout is not None

    async for raw_line in process.stdout:
        decoded = raw_line.decode().strip()

        if not decoded or '|' not in decoded:
            continue

        art_url, title, artist = decoded.split('|', 2)

        if not art_url:
            continue  # no image? skip event

        song_label = f'{title} – {artist}' if artist else title

        # Extension hook: track_change
        try:
            run_extension_hooks(
                'track_change', title=title, artist=artist, art_url=art_url
            )
        except Exception:
            pass

        print(
            f'[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]...'
        )

        await process_art_url(art_url, track_id=None)
        # Extension hook: track processing done, color will be handled in process_art_url
        # color_applied is triggered inside process_art_url after palette extraction

        print('[bold green]Processing done[/bold green].')
        print('[dim]' + '─' * 50 + '[/dim]')
        print('')

        if once:
            break
