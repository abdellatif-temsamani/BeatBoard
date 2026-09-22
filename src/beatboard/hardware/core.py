"""Core hardware loading – YAML plugins and fallback defaults."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .registry import _core_detect, hardware

_g213_script = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "G213Colors", "G213Colors.py"
)


def _resolve_core_command(template: list[str]) -> list[str]:
    """Resolve placeholders for core hardware commands."""
    resolved: list[str] = []
    for part in template:
        if part == "__python__":
            resolved.append(sys.executable)
        elif part == "__g213_script__":
            resolved.append(_g213_script)
        elif part == "__python":
            resolved.append(sys.executable)
        else:
            resolved.append(part)
    return resolved


def _find_core_plugins_dirs() -> list[Path]:
    """Return candidate core_plugins directories (package + project root)."""
    candidates: list[Path] = []
    pkg_dir = Path(__file__).parent.parent / "core_plugins"
    if pkg_dir.is_dir():
        candidates.append(pkg_dir)
    try:
        root_dir = Path(__file__).parent.parent.parent.parent / "core_plugins"
        if root_dir.is_dir() and root_dir.resolve() != pkg_dir.resolve():
            candidates.append(root_dir)
    except Exception:
        pass
    return candidates


def _load_core_hardware() -> None:
    """Populate hardware dict from core_plugins/*.yaml."""
    try:
        import yaml  # type: ignore

        from beatboard.plugins.models import validate_plugin_dict
    except Exception:
        return

    dirs = _find_core_plugins_dirs()
    seen: set[str] = set()
    priority_names = ["g213", "razer", "asus"]
    for d in dirs:
        all_files: dict[str, Path] = {}
        for pattern in ("*.yaml", "*.yml"):
            for p in d.glob(pattern):
                all_files[p.stem] = p
        ordered_paths: list[Path] = []
        for name in priority_names:
            if name in all_files:
                ordered_paths.append(all_files.pop(name))
        ordered_paths.extend(sorted(all_files.values(), key=lambda x: x.name))
        for p in ordered_paths:
            try:
                text = p.read_text(encoding="utf-8")
                data = yaml.safe_load(text)
                if data is None:
                    continue
                plugin = validate_plugin_dict(data, p, allow_reserved=True)
                if plugin.type != "hardware" or plugin.hardware is None:
                    continue
                if plugin.name in seen or plugin.name in hardware:
                    continue
                cmd = _resolve_core_command(plugin.hardware.command)
                hardware[plugin.name] = cmd
                if plugin.hardware.detect is not None:
                    _core_detect[plugin.name] = plugin.hardware.detect
                seen.add(plugin.name)
            except Exception:
                try:
                    from rich import print as _rprint

                    _rprint(f"[yellow]Warning:[/yellow] skipping core plugin {p.name}")
                except Exception:
                    pass
                continue


# Load core hardware at import time so hardware dict is ready for args parsing
_load_core_hardware()

# Fallback: if core dir missing or empty (e.g., minimal install), keep hardcoded defaults
if not hardware:
    hardware.update(
        {
            "g213": [sys.executable, _g213_script, "-c"],
            "razer": ["razer-cli", "-c"],
            "asus": ["asusctl", "aura", "static", "-c"],
        }
    )
    try:
        from beatboard.plugins.models import DetectSpec, UsbId

        _core_detect.setdefault(
            "g213", DetectSpec(usb=[UsbId(vendor=0x046D, product=0xC336)])
        )
        _core_detect.setdefault(
            "razer",
            DetectSpec(usb=[UsbId(vendor=0x1532)], executables=["razer-cli"]),
        )
        _core_detect.setdefault(
            "asus",
            DetectSpec(
                usb=[UsbId(vendor=0x0B05)],
                executables=["asusctl"],
                system_vendor="asus",
            ),
        )
    except Exception:
        pass
