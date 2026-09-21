from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal, Protocol

import usb.core

_g213_script = os.path.join(os.path.dirname(__file__), "G213Colors", "G213Colors.py")

hardware: dict[str, list[str]] = {
    "g213": [
        sys.executable,
        _g213_script,
        "-c",
    ],
    "razer": [
        "razer-cli",
        "-c",
    ],
    "asus": ["asusctl", "aura", "static", "-c"],
}

hardwareName = Literal["g213", "razer", "asus"]

_LOGITECH_VENDOR_ID = 0x046D
_G213_PRODUCT_ID = 0xC336
_RAZER_VENDOR_ID = 0x1532
_ASUS_VENDOR_ID = 0x0B05
_SYSTEM_VENDOR_PATHS = (
    Path("/sys/class/dmi/id/sys_vendor"),
    Path("/sys/devices/virtual/dmi/id/sys_vendor"),
)


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


def detect_hardware(
    *,
    devices: Iterable[USBDevice] | None = None,
    executable_finder: Callable[[str], str | None] | None = None,
    system_vendor: str | None = None,
) -> list[hardwareName]:
    """Detect supported hardware that BeatBoard can currently control.

    Logitech G213 keyboards are identified by their exact USB vendor and product
    IDs. Razer devices are identified by vendor ID and require ``razer-cli``.
    Asus hardware is identified through USB or the Linux system vendor and
    requires ``asusctl``.

    Args:
        devices: Optional USB device collection. When omitted, connected USB
            devices are enumerated with PyUSB.
        executable_finder: Function used to locate optional controller tools.
        system_vendor: Optional system vendor override. When omitted, Linux DMI
            information is used.

    Returns:
        Supported hardware names in stable registry order.
    """

    finder = executable_finder or shutil.which
    connected_devices = devices if devices is not None else _connected_usb_devices()
    try:
        usb_ids = {(device.idVendor, device.idProduct) for device in connected_devices}
    except (usb.core.NoBackendError, usb.core.USBError):
        usb_ids = set()
    detected: list[hardwareName] = []

    if (_LOGITECH_VENDOR_ID, _G213_PRODUCT_ID) in usb_ids:
        detected.append("g213")

    if any(vendor == _RAZER_VENDOR_ID for vendor, _ in usb_ids) and finder("razer-cli"):
        detected.append("razer")

    vendor_name = system_vendor if system_vendor is not None else _system_vendor()
    has_asus_hardware = any(vendor == _ASUS_VENDOR_ID for vendor, _ in usb_ids) or (
        "asus" in vendor_name.casefold()
    )
    if has_asus_hardware and finder("asusctl"):
        detected.append("asus")

    return detected


def get_command(names: list[hardwareName], color: str) -> list[list[str]]:
    """Get the command to run the hardware.

    Args:
        names: The names of the hardware to change the color of.
        color: The color to change the hardware to.

    Returns:
        list[list[str]]: The command to run the hardware.
    """

    commands: list[list[str]] = []
    for name in names:
        if name in hardware:
            commands.append(hardware[name] + [color])
        else:
            raise ValueError(f"Unknown hardware: {name}")
    return commands
