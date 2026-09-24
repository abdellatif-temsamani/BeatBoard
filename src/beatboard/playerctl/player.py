"""playerctl wrapper and availability check."""

from __future__ import annotations

import subprocess


def playerctl(*args: str) -> list[str]:
    """base playerctl command
        *args: playerctl arguments

    Returns: list[str]
    """
    return ['playerctl', '--player=spotify', *args]


def check_spotify_available() -> bool:
    """Check if Spotify player is available via playerctl.

    Returns: bool
    """
    try:
        result = subprocess.run(
            ['playerctl', '--list-all'], capture_output=True, text=True, timeout=5
        )
        return 'spotify' in result.stdout
    except (
        subprocess.TimeoutExpired,
        subprocess.CalledProcessError,
        FileNotFoundError,
    ):
        return False
