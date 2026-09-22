from __future__ import annotations

import os
import platform
import shutil
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal, Protocol

import usb.core

_g213_script = os.path.join(os.path.dirname(__file__), "G213Colors", "G213Colors.py")

# Core hardware is now defined in ./core_plugins/*.yaml and src/beatboard/core_plugins/*.yaml
# This dict is populated at import time from those YAML files.
hardware: dict[str, list[str]] = {}

hardwareName = Literal["g213", "razer", "asus"]
# Core + plugin-provided hardware (populated at runtime)
_core_detect: dict[str, object] = {}  # DetectSpec for core hardware
_plugin_hardware: dict[str, list[str]] = {}
_plugin_detect: dict[str, object] = {}  # DetectSpec stored as opaque for detection


def _get_plugin_detect(name: str):
    return _plugin_detect.get(name)


_SYSTEM_VENDOR_PATHS = (
    Path("/sys/class/dmi/id/sys_vendor"),
    Path("/sys/devices/virtual/dmi/id/sys_vendor"),
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
    pkg_dir = Path(__file__).parent / "core_plugins"
    if pkg_dir.is_dir():
        candidates.append(pkg_dir)
    try:
        root_dir = Path(__file__).parent.parent.parent / "core_plugins"
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


def is_windows() -> bool:
    """Check if the current platform is Windows."""
    return platform.system() == "Windows"


def is_linux() -> bool:
    """Check if the current platform is Linux."""
    return platform.system() == "Linux"


class USBDevice(Protocol):
    """USB device attributes used during hardware detection."""

    idVendor: int
    idProduct: int


def _connected_usb_devices() -> Iterable[USBDevice]:
    """Return connected USB devices, or an empty collection if USB is unavailable."""
    try:
        return usb.core.find(find_all=True) or ()
    except (usb.core.NoBackendError, usb.core.USBError):
        return ()


def _system_vendor() -> str:
    """Read the system vendor exposed by Linux DMI, when available."""
    for path in _SYSTEM_VENDOR_PATHS:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
    return ""


def register_plugin_hardware(
    name: str,
    command: list[str],
    detect: object | None = None,
) -> None:
    """Register a community plugin hardware driver.

    Args:
        name: Unique plugin hardware name (slug).
        command: Command template (list[str]), may contain ``{color}`` placeholder.
        detect: Optional DetectSpec from plugin models.

    Raises:
        ValueError: If name conflicts with built-in or already registered plugin.
    """
    if name in hardware:
        raise ValueError(f"plugin hardware name '{name}' conflicts with built-in")
    if name in _plugin_hardware:
        raise ValueError(f"plugin hardware name '{name}' already registered")
    if not command or not all(isinstance(c, str) and c for c in command):
        raise ValueError("command must be non-empty list of strings")
    _plugin_hardware[name] = list(command)
    if detect is not None:
        _plugin_detect[name] = detect


def clear_plugin_hardware() -> None:
    """Clear all plugin hardware registrations (for tests)."""
    _plugin_hardware.clear()
    _plugin_detect.clear()


def get_all_hardware() -> dict[str, list[str]]:
    """Return combined built-in + plugin hardware registry."""
    return {**hardware, **_plugin_hardware}


def get_all_hardware_names() -> list[str]:
    """Return sorted list of all available hardware names (built-in + plugins)."""
    return sorted(get_all_hardware().keys())


def is_plugin_hardware(name: str) -> bool:
    return name in _plugin_hardware


def _plugin_matches_detect(
    detect: object,
    usb_ids: set[tuple[int, int]],
    system_vendor: str,
    finder: Callable[[str], str | None],
) -> bool:
    """Evaluate a plugin DetectSpec against current system state.

    Semantics:
      - Executables: all must be found.
      - If both usb and system_vendor are present: require (usb_match OR vendor_match) AND executables.
      - If only one of usb/system_vendor present: require that one AND executables.
      - If neither usb nor vendor, require executables (if any) – otherwise manual-only (caller should skip).
      - On Windows, USB/vendor checks are ignored and only executables matter (g213-like usb-only without exe never auto-detects).
    """
    try:
        from beatboard.plugins.models import DetectSpec  # type: ignore
    except Exception:
        return False

    if not isinstance(detect, DetectSpec):
        return False

    if is_windows():
        if detect.executables:
            for exe in detect.executables:
                if not finder(exe):
                    return False
            return True
        return False

    if detect.executables:
        for exe in detect.executables:
            if not finder(exe):
                return False

    has_usb = bool(detect.usb)
    has_vendor = detect.system_vendor is not None

    def _usb_matched() -> bool:
        for entry in detect.usb:  # type: ignore[union-attr]
            if entry.product is not None:
                if (entry.vendor, entry.product) in usb_ids:
                    return True
            else:
                if any(v == entry.vendor for v, _ in usb_ids):
                    return True
        return False

    if has_usb and has_vendor:
        usb_matched = _usb_matched()
        vendor_matched = detect.system_vendor.casefold() in system_vendor.casefold()  # type: ignore[union-attr]
        if not (usb_matched or vendor_matched):
            return False
    elif has_usb:
        if not _usb_matched():
            return False
    elif has_vendor:
        if detect.system_vendor.casefold() not in system_vendor.casefold():  # type: ignore[union-attr]
            return False

    return True


def detect_hardware(
    *,
    devices: Iterable[USBDevice] | None = None,
    executable_finder: Callable[[str], str | None] | None = None,
    system_vendor: str | None = None,
) -> list[str]:
    """Detect supported hardware that BeatBoard can currently control.

    Core hardware (g213/razer/asus) is now defined in core_plugins/*.yaml and
    evaluated via the same plugin matching engine as community plugins.

    On Windows, USB detection may be limited and system vendor detection is not
    available. Manual hardware specification with ``--hardware`` is recommended.

    Plugin hardware is also evaluated: each plugin declares optional USB IDs,
    required executables, and system vendor substrings.

    Args:
        devices: Optional USB device collection. When omitted, connected USB
            devices are enumerated with PyUSB (Linux only).
        executable_finder: Function used to locate optional controller tools.
        system_vendor: Optional system vendor override. When omitted, Linux DMI
            information is used (Linux only).

    Returns:
        Supported hardware names in stable registry order (core first, then plugins sorted).
    """
    finder = executable_finder or shutil.which
    detected: list[str] = []

    # Debug helper - only for -d all to minimize noise
    try:
        from .globs import Globs

        _dbg = Globs().debug.get("all")
    except Exception:
        _dbg = False

    if is_windows():
        vendor_name_win = system_vendor if system_vendor is not None else ""
        usb_ids_win: set[tuple[int, int]] = set()
        core_order = ["g213", "razer", "asus"]
        for name in core_order:
            if name in hardware:
                spec = _core_detect.get(name)
                if spec is None:
                    continue
                if _plugin_matches_detect(spec, usb_ids_win, vendor_name_win, finder):
                    detected.append(name)  # type: ignore[arg-type]
        for name in sorted(hardware.keys()):
            if name in core_order:
                continue
            spec = _core_detect.get(name)
            if spec is None:
                continue
            if _plugin_matches_detect(spec, usb_ids_win, vendor_name_win, finder):
                detected.append(name)  # type: ignore[arg-type]
        try:
            for pname in sorted(_plugin_hardware.keys()):
                spec = _plugin_detect.get(pname)
                if spec is None:
                    continue
                if _plugin_matches_detect(spec, usb_ids_win, vendor_name_win, finder):
                    detected.append(pname)  # type: ignore[arg-type]
        except Exception:
            pass
        return detected  # type: ignore[return-value]

    connected_devices = devices if devices is not None else _connected_usb_devices()
    try:
        usb_ids = {(device.idVendor, device.idProduct) for device in connected_devices}
    except (usb.core.NoBackendError, usb.core.USBError):
        usb_ids = set()

    vendor_name = system_vendor if system_vendor is not None else _system_vendor()

    if _dbg:
        try:
            from rich import print as _rprint

            _rprint(
                f"[dim]detect: usb_ids={sorted(usb_ids)[:10]} vendor='{vendor_name[:30]}' razer-cli={finder('razer-cli')} asusctl={finder('asusctl')} g213_ids={(0x046D, 0xC336) in usb_ids}[/dim]"
            )
        except Exception:
            pass

    core_order = ["g213", "razer", "asus"]
    for name in core_order:
        if name in hardware:
            spec = _core_detect.get(name)
            if spec is None:
                continue
            if _plugin_matches_detect(spec, usb_ids, vendor_name, finder):
                detected.append(name)  # type: ignore[arg-type]
    for name in sorted(hardware.keys()):
        if name in core_order:
            continue
        spec = _core_detect.get(name)
        if spec is None:
            continue
        if _plugin_matches_detect(spec, usb_ids, vendor_name, finder):
            detected.append(name)  # type: ignore[arg-type]

    for pname in sorted(_plugin_hardware.keys()):
        spec = _plugin_detect.get(pname)
        if spec is None:
            continue
        if _plugin_matches_detect(spec, usb_ids, vendor_name, finder):
            detected.append(pname)  # type: ignore[arg-type]

    return detected  # type: ignore[return-value]


def _build_plugin_command(template: list[str], color: str) -> list[str]:
    """Build plugin command, handling {color} placeholder."""
    has_placeholder = any("{color}" in part for part in template)
    if has_placeholder:
        built = [
            part.replace("{color}", color).replace("{hex}", color) for part in template
        ]
        return built
    return template + [color]


def get_command(names: list[hardwareName] | list[str], color: str) -> list[list[str]]:
    """Get the command to run the hardware.

    Args:
        names: The names of the hardware to change the color of (built-in or plugin).
        color: The color to change the hardware to (hex without '#', e.g. 'ff0000').

    Returns:
        list[list[str]]: The command to run the hardware.
    """
    if not isinstance(color, str) or len(color) != 6:
        pass

    commands: list[list[str]] = []
    combined = get_all_hardware()
    for name in names:
        if name in combined:
            if name in _plugin_hardware:
                commands.append(_build_plugin_command(_plugin_hardware[name], color))
            else:
                commands.append(hardware[name] + [color])
        else:
            raise ValueError(f"Unknown hardware: {name}")
    return commands
