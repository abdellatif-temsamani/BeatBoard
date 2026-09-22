from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from rich import print as rprint

from ..globs import Globs
from .registry import extension_registry


def _expand_command(template: list[str], context: dict[str, str]) -> list[str]:
    """Replace {color}, {title}, {artist}, {hex} etc in command template."""
    expanded: list[str] = []
    for part in template:
        out = part
        for k, v in context.items():
            out = out.replace(f"{{{k}}}", v)
            # also support {hex} as alias for color
            if k == "color":
                out = out.replace("{hex}", v)
        expanded.append(out)
    return expanded


def run_extension_hooks(event: str, **context: str) -> None:
    """Run all extension hooks for event.

    Args:
        event: One of track_change, color_applied, pre_color, post_color
        context: Variables for template expansion (title, artist, color, art_url, etc.)
    """
    globs = Globs()
    # Only run if debug or not? Always run, but log when plugins debug is on
    debug = globs.debug.get("plugins") or globs.debug.get("all")
    for name, plugin in extension_registry.items():
        if plugin.extension is None:
            continue
        for hook in plugin.extension.hooks:
            if hook.event != event:
                continue
            cmd = _expand_command(hook.command, context)
            if not cmd:
                continue
            if debug:
                rprint(f"[dim]extension:{name} event:{event} → {' '.join(cmd)}[/dim]")
            # Check executable exists
            if not (shutil.which(cmd[0]) or Path(cmd[0]).exists()):
                if debug:
                    rprint(f"[dim]extension:{name} skip, not found: {cmd[0]}[/dim]")
                continue
            try:
                subprocess.run(cmd, check=False, timeout=5)
            except Exception as exc:
                if debug:
                    rprint(f"[yellow]extension:{name} failed: {exc}[/yellow]")
