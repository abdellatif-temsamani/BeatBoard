"""Hardware color application with deduplicated execution helper."""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time

from rich import print

from ..globs import Globs
from ..hardware import get_command


async def _run_hardware(color: str) -> None:
    """Run hardware commands for a single hex color (deduplicated helper).

    Filters unavailable commands, prints debug if enabled, and runs
    remaining commands concurrently. Used by both ``apply_colors`` and
    ``process_art_url`` fast-path / main path to avoid duplicated logic.

    Args:
        color: Hex color without '#', e.g. 'ff0000'.
    """
    globs = Globs()
    commands = get_command(globs.hardware, color)
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

        async def _run(cmd: list[str]):
            try:
                await asyncio.to_thread(subprocess.run, cmd)
            except Exception as e:
                print(f"[bold red]Error:[/bold red] running hardware command: {e}")

        if len(runnable) == 1:
            await _run(runnable[0])
        else:
            await asyncio.gather(*(_run(c) for c in runnable))


async def apply_colors(hex_colors: list[str]) -> None:
    """Apply given colors to hardware (no image fetch).

    Used for fast cache-hit path (e.g. track cache) to skip palette extraction.
    Hardware commands are run concurrently when multiple devices are present.
    """
    globs = Globs()
    start_hw = time.time()
    if not hex_colors:
        hex_colors = ["ffffff"]
    await _run_hardware(hex_colors[0])
    if globs.debug.get("perf") or globs.debug.get("all"):
        hw_ms = (time.time() - start_hw) * 1000
        print(f"[cyan]perf[/cyan] [dim]·[/dim] hw [cyan]{hw_ms:.0f}ms[/cyan]")
