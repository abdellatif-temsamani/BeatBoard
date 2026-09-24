"""Hardware detection – USB / vendor / executable matching."""

from __future__ import annotations

import shutil
from collections.abc import Callable, Iterable

import usb.core

from .platform import _connected_usb_devices, _system_vendor
from .registry import _core_detect, _plugin_detect, _plugin_hardware, hardware


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

    # Use package is_windows to respect patch on beatboard.hardware.is_windows
    try:
        from beatboard.hardware import is_windows as _is_windows  # type: ignore
    except Exception:
        from .platform import is_windows as _is_windows  # fallback

    if _is_windows():
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
    devices: Iterable[object] | None = None,
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
    # Dynamic lookup for is_windows to respect patch on beatboard.hardware.is_windows
    try:
        from beatboard.hardware import is_windows as _is_windows  # type: ignore
    except Exception:
        from .platform import is_windows as _is_windows  # fallback

    finder = executable_finder or shutil.which
    detected: list[str] = []

    # Debug helper - only for -d all to minimize noise
    try:
        from ..globs import Globs

        _dbg = Globs().debug.get('all')
    except Exception:
        _dbg = False

    if _is_windows():
        vendor_name_win = system_vendor if system_vendor is not None else ''
        usb_ids_win: set[tuple[int, int]] = set()
        core_order = ['g213', 'razer', 'asus']
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
        usb_ids = {(device.idVendor, device.idProduct) for device in connected_devices}  # type: ignore[attr-defined]
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

    core_order = ['g213', 'razer', 'asus']
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
