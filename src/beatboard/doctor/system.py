"""System diagnostics – platform, Python, BeatBoard version."""

from __future__ import annotations

import platform
import sys
from pathlib import Path


def diagnose_system() -> list[dict[str, str]]:
    """Return system check results."""
    results: list[dict[str, str]] = []
    # BeatBoard version
    try:
        from beatboard._version import __version__

        ver = __version__
    except Exception:
        ver = 'unknown'
    results.append(
        {
            'check': 'BeatBoard version',
            'status': 'ok',
            'detail': ver,
            'hint': '',
        }
    )
    # Python version
    py_ver = platform.python_version()
    py_ok = sys.version_info >= (3, 11)
    results.append(
        {
            'check': 'Python',
            'status': 'ok' if py_ok else 'fail',
            'detail': f'{py_ver} ({sys.executable})',
            'hint': '' if py_ok else 'Requires Python >=3.11',
        }
    )
    # OS
    os_name = platform.system() or 'unknown'
    os_rel = platform.release() or ''
    arch = platform.machine() or ''
    results.append(
        {
            'check': 'OS',
            'status': 'ok',
            'detail': f'{os_name} {os_rel} ({arch})'.strip(),
            'hint': '',
        }
    )
    # Platform module
    try:
        from beatboard.hardware.platform import is_linux, is_windows, system

        sys_name = system()
        is_lin = is_linux()
        is_win = is_windows()
        results.append(
            {
                'check': 'Platform detection',
                'status': 'ok',
                'detail': f'system()={sys_name} linux={is_lin} windows={is_win}',
                'hint': '',
            }
        )
    except Exception as exc:
        results.append(
            {
                'check': 'Platform detection',
                'status': 'fail',
                'detail': f'error: {exc}',
                'hint': 'Check hardware/platform.py import',
            }
        )
    # Install location
    try:
        import beatboard

        loc = Path(beatboard.__file__).resolve().parent
        results.append(
            {
                'check': 'Install location',
                'status': 'ok',
                'detail': str(loc),
                'hint': '',
            }
        )
    except Exception as exc:
        results.append(
            {
                'check': 'Install location',
                'status': 'warn',
                'detail': str(exc),
                'hint': '',
            }
        )
    return results
