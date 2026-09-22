"""Hardware diagnostics – registry, detection, commands."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def diagnose_hardware() -> list[dict[str, str]]:
    """Check hardware registry and detection."""
    results: list[dict[str, str]] = []
    # Registry
    try:
        from beatboard.hardware import get_all_hardware, hardware
        from beatboard.hardware.registry import (
            _core_detect,
            _plugin_detect,
            _plugin_hardware,
        )
        from beatboard.hardware.platform import is_linux, is_windows, system

        all_hw = get_all_hardware()
        builtin = list(hardware.keys())
        plugins = list(_plugin_hardware.keys())
        results.append(
            {
                "check": "Hardware registry",
                "status": "ok" if all_hw else "warn",
                "detail": f"builtin={builtin} plugins={plugins} total={len(all_hw)}",
                "hint": "" if all_hw else "No hardware registered – check core_plugins",
            }
        )
        # Core detect info
        core_detect_keys = list(_core_detect.keys())
        plugin_detect_keys = list(_plugin_detect.keys())
        results.append(
            {
                "check": "Detect specs",
                "status": "ok",
                "detail": f"core={core_detect_keys} plugin={plugin_detect_keys}",
                "hint": "",
            }
        )
        # Platform
        results.append(
            {
                "check": "Platform",
                "status": "ok",
                "detail": f"system={system()} linux={is_linux()} windows={is_windows()}",
                "hint": "",
            }
        )
    except Exception as exc:
        results.append(
            {
                "check": "Hardware registry",
                "status": "fail",
                "detail": str(exc),
                "hint": "Check hardware package import",
            }
        )
        return results

    # Executables for each hardware
    try:
        from beatboard.hardware import get_all_hardware
        from beatboard.hardware.commands import _build_plugin_command
        from beatboard.hardware.core import _g213_script

        _ = _build_plugin_command  # keep import used
        all_hw = get_all_hardware()
        for name, cmd in all_hw.items():
            # cmd is list[str]
            exe = cmd[0] if cmd else ""
            # Resolve placeholders: __python__ / __g213_script__ already resolved in registry
            # For g213, exe is sys.executable
            if exe == sys.executable:
                exists = Path(exe).is_file()
                found = exe if exists else None
                detail = f"{exe} {'found' if exists else 'missing'}"
                status = "ok" if exists else "fail"
                hint = (
                    "" if exists else "Python executable not found – reinstall Python"
                )
            elif exe == _g213_script or exe.endswith("G213Colors.py"):
                exists = Path(exe).is_file()
                status = "ok" if exists else "warn"
                detail = f"{exe} {'exists' if exists else 'missing'}"
                hint = "" if exists else "Reinstall BeatBoard"
            else:
                found = shutil.which(exe) if exe else None
                # for razer/asus, tool may not be installed – info not fail if not needed
                status = "ok" if found else "warn"
                detail = found or f"{exe} not found in PATH"
                hint = "" if found else f"Install {exe} for {name} support"
            results.append(
                {
                    "check": f"Hardware '{name}' command",
                    "status": status,
                    "detail": f"{cmd} -> {detail}",
                    "hint": hint,
                }
            )
    except Exception as exc:
        results.append(
            {
                "check": "Hardware commands",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # Detection
    try:
        from beatboard.hardware import detect_hardware
        from beatboard.hardware.platform import _connected_usb_devices, _system_vendor

        # Try to get USB ids
        try:
            devices = list(_connected_usb_devices())
            usb_detail = f"{len(devices)} device(s)"
            if devices:
                ids = [
                    (getattr(d, "idVendor", "?"), getattr(d, "idProduct", "?"))
                    for d in devices[:5]
                ]
                usb_detail += f" e.g. {ids}"
        except Exception as exc:
            usb_detail = f"error: {exc}"
        results.append(
            {
                "check": "USB enumeration",
                "status": "ok",
                "detail": usb_detail,
                "hint": "",
            }
        )

        try:
            vendor = _system_vendor()
            results.append(
                {
                    "check": "System vendor",
                    "status": "ok" if vendor else "info",
                    "detail": vendor or "(empty – not Linux or no DMI)",
                    "hint": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "check": "System vendor",
                    "status": "warn",
                    "detail": str(exc),
                    "hint": "",
                }
            )

        try:
            detected = detect_hardware()
            status = "ok" if detected else "warn"
            detail = ", ".join(detected) if detected else "none detected"
            hint = (
                ""
                if detected
                else "Connect supported hardware or use --hardware <name>"
            )
            results.append(
                {
                    "check": "Detected hardware",
                    "status": status,
                    "detail": detail,
                    "hint": hint,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "check": "Detected hardware",
                    "status": "fail",
                    "detail": str(exc),
                    "hint": "Check detect_hardware() logic",
                }
            )

        # Cached hardware
        try:
            from beatboard.cache.db import get_cached_hardware

            cached = get_cached_hardware()
            results.append(
                {
                    "check": "Cached hardware (DB)",
                    "status": "ok" if cached else "info",
                    "detail": ", ".join(cached) if cached else "empty",
                    "hint": "" if cached else "Will auto-detect on next run",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "check": "Cached hardware (DB)",
                    "status": "warn",
                    "detail": str(exc),
                    "hint": "",
                }
            )

        # get_command dry-run
        try:
            from beatboard.hardware import get_command

            if detected:
                cmds = get_command(detected, "ff0000")
                results.append(
                    {
                        "check": "Command build (test)",
                        "status": "ok",
                        "detail": f"{len(cmds)} command(s) for color ff0000",
                        "hint": "",
                    }
                )
            else:
                results.append(
                    {
                        "check": "Command build (test)",
                        "status": "info",
                        "detail": "skipped – no detected hardware",
                        "hint": "Specify --hardware to test manually",
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "check": "Command build (test)",
                    "status": "fail",
                    "detail": str(exc),
                    "hint": "",
                }
            )

    except Exception as exc:
        results.append(
            {
                "check": "Hardware detection",
                "status": "fail",
                "detail": str(exc),
                "hint": "",
            }
        )

    return results
