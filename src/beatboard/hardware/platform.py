"""Platform helpers – USB and OS detection."""

from __future__ import annotations

import platform as _stdlib_platform
from collections.abc import Iterable
from typing import Protocol

import usb.core

from .constants import _SYSTEM_VENDOR_PATHS

# Expose system for test patching (beatboard.hardware.platform.system)
system = _stdlib_platform.system


def is_windows() -> bool:
    """Check if the current platform is Windows."""
    return system() == 'Windows'


def is_linux() -> bool:
    """Check if the current platform is Linux."""
    return system() == 'Linux'


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
            return path.read_text(encoding='utf-8').strip()
        except OSError:
            continue
    return ''
