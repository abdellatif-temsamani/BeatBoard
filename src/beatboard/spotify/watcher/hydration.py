"""Initial hydration – single REST call before Dealer push."""

from __future__ import annotations

import asyncio
import time

from rich import print

from ...globs import Globs
from ...logs import log
from ..api import _fetch_current_playback_sync
from ..auth import ensure_valid_token
from ..constants import _UNAUTHORIZED


async def _hydrate_initial(
    token: str,
    globs: Globs,
    once: bool,
) -> tuple[str, str | None, bool]:
    """Hydrate initial track via REST, handling 401 refresh.

    Returns:
        Tuple of (possibly refreshed token, last_art_url, should_exit).
        ``should_exit`` is True when ``once`` and an initial track was
        processed – caller should return immediately.
    """
    last_art_url: str | None = None
    should_exit = False
    try:
        current = await asyncio.to_thread(_fetch_current_playback_sync, token)
        if current is _UNAUTHORIZED:
            log("api", "[yellow]api[/yellow] [dim]·[/dim] now playing 401, refreshing…")
            try:
                refreshed = ensure_valid_token(
                    config_path=getattr(globs, "config_path", None),
                    force_refresh=True,
                )
                if refreshed and refreshed != token:
                    token = refreshed
                    current = await asyncio.to_thread(
                        _fetch_current_playback_sync, token
                    )
                    if current is not None and current is not _UNAUTHORIZED:
                        log(
                            "api",
                            "[green]api[/green] [dim]·[/dim] now playing retry after refresh [green]ok[/green]",
                        )
                    elif current is _UNAUTHORIZED:
                        log(
                            "api",
                            "[red]api[/red] [dim]·[/dim] still 401 after refresh",
                        )
                        current = None
                    else:
                        pass
                elif refreshed and refreshed == token:
                    current = await asyncio.to_thread(
                        _fetch_current_playback_sync, token
                    )
                    if current is _UNAUTHORIZED:
                        current = None
                else:
                    current = None
            except Exception:
                current = None
        if current is not None and current is not _UNAUTHORIZED:
            art_url, title, artist = current  # type: ignore[misc]
            if art_url:
                last_art_url = art_url
                song_label = ""
                if title and artist:
                    song_label = f"{title} – {artist}"
                elif title:
                    song_label = title
                elif artist:
                    song_label = artist
                else:
                    song_label = "Unknown track"
                print(
                    f"[bold yellow]Processing[/bold yellow] [bold green]{song_label}[/bold green]..."
                )
                try:
                    from ...plugins.hooks import run_extension_hooks

                    run_extension_hooks(
                        "track_change",
                        title=title or "",
                        artist=artist or "",
                        art_url=art_url or "",
                    )
                except Exception:
                    pass
                init_t0 = time.perf_counter()
                from ...playerctl import process_art_url

                await process_art_url(art_url)
                init_dt = (time.perf_counter() - init_t0) * 1000
                log(
                    "api",
                    f"[blue]ws[/blue] [dim]·[/dim] initial [green]{song_label}[/green] [dim]·[/dim] [cyan]{init_dt:.0f}ms[/cyan]",
                )
                print("[bold green]Processing done[/bold green].")
                print("[dim]" + "─" * 50 + "[/dim]")
                print("")
                if once:
                    should_exit = True
            else:
                log("api", "[yellow]ws[/yellow] [dim]·[/dim] initial no artwork, skip")
        else:
            log("api", "[blue]ws[/blue] [dim]·[/dim] initial nothing playing")
    except Exception as exc:
        log("api", f"[red]ws[/red] [dim]·[/dim] initial error: {exc}")
    return token, last_art_url, should_exit


__all__ = ["_hydrate_initial"]
