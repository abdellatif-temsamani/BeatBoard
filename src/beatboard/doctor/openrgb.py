"""OpenRGB diagnostics – binary, server, SDK."""

from __future__ import annotations

import shutil
import socket
import subprocess


def diagnose_openrgb() -> list[dict[str, str]]:
    """Check OpenRGB integration (optional, not required for core hardware)."""
    results: list[dict[str, str]] = []

    # Check binaries
    for exe in ("openrgb", "openrgb-cli"):
        found = shutil.which(exe)
        results.append(
            {
                "check": f"OpenRGB binary '{exe}'",
                "status": "ok" if found else "info",
                "detail": found or "not found (optional)",
                "hint": ""
                if found
                else "Install OpenRGB for generic RGB: https://openrgb.org",
            }
        )

    # Try openrgb --version if found
    which_openrgb = shutil.which("openrgb")
    if which_openrgb:
        try:
            out = subprocess.run(
                [which_openrgb, "--version"], capture_output=True, text=True, timeout=3
            )
            detail = (out.stdout.strip() or out.stderr.strip() or "executed")[:120]
            status = "ok" if out.returncode == 0 else "warn"
            results.append(
                {
                    "check": "openrgb --version",
                    "status": status,
                    "detail": detail,
                    "hint": "",
                }
            )
        except Exception as exc:
            results.append(
                {
                    "check": "openrgb --version",
                    "status": "warn",
                    "detail": str(exc),
                    "hint": "",
                }
            )
    else:
        results.append(
            {
                "check": "openrgb --version",
                "status": "info",
                "detail": "skipped – binary not found",
                "hint": "",
            }
        )

    # Check SDK server on typical port 6742
    # OpenRGB SDK runs on localhost:6742 when "Enable Server" is ticked
    for port in (6742,):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            rc = sock.connect_ex(("127.0.0.1", port))
            sock.close()
            if rc == 0:
                results.append(
                    {
                        "check": f"OpenRGB SDK port {port}",
                        "status": "ok",
                        "detail": f"localhost:{port} reachable (SDK enabled)",
                        "hint": "",
                    }
                )
            else:
                results.append(
                    {
                        "check": f"OpenRGB SDK port {port}",
                        "status": "info",
                        "detail": f"localhost:{port} not open (SDK disabled or OpenRGB not running)",
                        "hint": "Enable OpenRGB SDK Server in settings if using OpenRGB hardware",
                    }
                )
        except Exception as exc:
            results.append(
                {
                    "check": f"OpenRGB SDK port {port}",
                    "status": "info",
                    "detail": str(exc),
                    "hint": "",
                }
            )

    # Check python openrgb library if installed
    try:
        import importlib.util

        spec = importlib.util.find_spec("openrgb")
        if spec is not None:
            results.append(
                {
                    "check": "Python openrgb lib",
                    "status": "ok",
                    "detail": "installed",
                    "hint": "",
                }
            )
        else:
            results.append(
                {
                    "check": "Python openrgb lib",
                    "status": "info",
                    "detail": "not installed (optional)",
                    "hint": "pip install openrgb-python if you need SDK control",
                }
            )
    except Exception as exc:
        results.append(
            {
                "check": "Python openrgb lib",
                "status": "info",
                "detail": str(exc),
                "hint": "",
            }
        )

    # Note about core hardware vs OpenRGB
    results.append(
        {
            "check": "OpenRGB vs BeatBoard",
            "status": "info",
            "detail": "BeatBoard uses direct drivers (g213/razer/asus); OpenRGB is optional generic backend",
            "hint": "Create a plugin YAML with openrgb command if needed",
        }
    )
    return results
