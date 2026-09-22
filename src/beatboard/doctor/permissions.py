"""Permissions diagnostics – file perms, USB, groups."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def diagnose_permissions(
    config_path: Path | None = None, cache_path_str: str | None = None
) -> list[dict[str, str]]:
    """Check filesystem and USB permissions."""
    results: list[dict[str, str]] = []

    # Config and cache dirs writable – already covered but re-emphasize
    try:
        from beatboard.config import get_config_path

        cfg_path = config_path or get_config_path()
        cfg_dir = cfg_path.parent
        exists = cfg_dir.exists()
        writable = os.access(cfg_dir, os.W_OK) if exists else False
        # also check if parent can be created
        results.append(
            {
                "check": "Config dir",
                "status": "ok" if exists and writable else "warn" if exists else "warn",
                "detail": f"{cfg_dir} {'writable' if writable else 'not writable' if exists else 'missing – will be created'}",
                "hint": ""
                if writable
                else f"mkdir -p {cfg_dir} && chmod u+w {cfg_dir}",
            }
        )
    except Exception as exc:
        results.append(
            {"check": "Config dir", "status": "warn", "detail": str(exc), "hint": ""}
        )

    try:
        from beatboard.globs import Globs, get_cache_db

        cp = cache_path_str or Globs().cache_path or get_cache_db()
        cp_path = Path(cp).expanduser()
        parent = cp_path.parent
        exists = parent.exists()
        writable = os.access(parent, os.W_OK) if exists else False
        results.append(
            {
                "check": "Cache dir perms",
                "status": "ok" if exists and writable else "warn" if exists else "warn",
                "detail": f"{parent} {'writable' if writable else 'not writable' if exists else 'missing'}",
                "hint": "" if writable else f"mkdir -p {parent}",
            }
        )
    except Exception as exc:
        results.append(
            {
                "check": "Cache dir perms",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # Running as root?
    try:
        is_root = False
        if hasattr(os, "geteuid"):
            is_root = os.geteuid() == 0  # type: ignore[attr-defined]
        detail = (
            "running as root"
            if is_root
            else f"uid={os.getuid() if hasattr(os, 'getuid') else 'unknown'}"
        )
        # root not required, but warn if not root and hardware needs USB
        results.append(
            {
                "check": "User privileges",
                "status": "ok",
                "detail": detail,
                "hint": "Root not required; USB may need udev rules",
            }
        )
    except Exception as exc:
        results.append(
            {
                "check": "User privileges",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # Input group (Linux – needed for HID)
    try:
        import platform as _plat

        if _plat.system() == "Linux":
            # Check groups
            try:
                grp_out = subprocess.run(
                    ["groups"], capture_output=True, text=True, timeout=2
                )
                groups = grp_out.stdout.strip() if grp_out.returncode == 0 else ""
                has_input = "input" in groups
                has_plugdev = "plugdev" in groups
                detail = groups if groups else "could not determine groups"
                status = (
                    "ok" if (has_input or has_plugdev or "root" in groups) else "warn"
                )
                hint = (
                    ""
                    if status == "ok"
                    else "Consider: sudo usermod -a -G input $USER (re-login)"
                )
                results.append(
                    {
                        "check": "Linux groups",
                        "status": status,
                        "detail": detail
                        + f" (input={has_input} plugdev={has_plugdev})",
                        "hint": hint,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "check": "Linux groups",
                        "status": "warn",
                        "detail": str(exc),
                        "hint": "",
                    }
                )
            # udev accessibility: check /dev/bus/usb
            usb_path = Path("/dev/bus/usb")
            if usb_path.exists():
                try:
                    # try listing
                    accessible = os.access(usb_path, os.R_OK)
                    results.append(
                        {
                            "check": "USB bus access",
                            "status": "ok" if accessible else "warn",
                            "detail": f"{usb_path} {'readable' if accessible else 'not readable'}",
                            "hint": ""
                            if accessible
                            else "Check udev rules or run with sudo for G213",
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "check": "USB bus access",
                            "status": "warn",
                            "detail": str(exc),
                            "hint": "",
                        }
                    )
            else:
                results.append(
                    {
                        "check": "USB bus access",
                        "status": "warn",
                        "detail": "/dev/bus/usb not found",
                        "hint": "Non-Linux or limited container",
                    }
                )
        else:
            results.append(
                {
                    "check": "Linux groups",
                    "status": "info",
                    "detail": f"skipped (not Linux: {_plat.system()})",
                    "hint": "",
                }
            )
    except Exception as exc:
        results.append(
            {"check": "Linux groups", "status": "warn", "detail": str(exc), "hint": ""}
        )

    # Check G213 script permission
    try:
        from beatboard.hardware.core import _g213_script

        p = Path(_g213_script)
        exists = p.is_file()
        results.append(
            {
                "check": "G213Colors script",
                "status": "ok" if exists else "warn",
                "detail": str(p) + (" exists" if exists else " missing"),
                "hint": "" if exists else "Reinstall BeatBoard; G213 driver missing",
            }
        )
        if exists:
            readable = os.access(p, os.R_OK)
            results.append(
                {
                    "check": "G213Colors readable",
                    "status": "ok" if readable else "fail",
                    "detail": "readable" if readable else "not readable",
                    "hint": "" if readable else f"chmod 644 {p}",
                }
            )
    except Exception as exc:
        results.append(
            {
                "check": "G213Colors script",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # Check plugin dir writable
    try:
        from beatboard.globs import Globs

        pdir = Globs().plugin_dir
        if pdir:
            pp = Path(pdir).expanduser()
            exists = pp.exists()
            writable = os.access(pp, os.W_OK) if exists else False
            # if not exists it will be created
            status = "ok" if (not exists or writable) else "warn"
            results.append(
                {
                    "check": "Plugin dir writable",
                    "status": status,
                    "detail": f"{pp} {'writable' if writable else 'not writable' if exists else 'will be created'}",
                    "hint": "" if status == "ok" else f"chmod u+w {pp}",
                }
            )
        else:
            results.append(
                {
                    "check": "Plugin dir",
                    "status": "info",
                    "detail": "disabled (plugin_dir=null)",
                    "hint": "",
                }
            )
    except Exception as exc:
        results.append(
            {
                "check": "Plugin dir writable",
                "status": "warn",
                "detail": str(exc),
                "hint": "",
            }
        )

    # Which executables needed?
    for exe in ("playerctl", "razer-cli", "asusctl"):
        found = shutil.which(exe)
        results.append(
            {
                "check": f"Executable {exe}",
                "status": "ok" if found else "info",
                "detail": found or "not found in PATH",
                "hint": "" if found else f"Install {exe} if you use related hardware",
            }
        )

    return results
