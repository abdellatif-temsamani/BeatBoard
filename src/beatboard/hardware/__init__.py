"""Hardware integration for BeatBoard.

Modular package split from the former ``hardware.py`` monolith.
Public facade re-exports the original flat API for backward compatibility.
"""

from __future__ import annotations

import os

# --- constants (leaf) ---
from .constants import _SYSTEM_VENDOR_PATHS

# --- registry (single source for mutable state) ---
from .registry import (
    _core_detect,
    _get_plugin_detect,
    _plugin_detect,
    _plugin_hardware,
    clear_plugin_hardware,
    get_all_hardware,
    get_all_hardware_names,
    hardware,
    is_plugin_hardware,
    register_plugin_hardware,
)

# --- core (populates registry) ---
from .core import (
    _find_core_plugins_dirs,
    _g213_script,
    _load_core_hardware,
    _resolve_core_command,
)

# --- platform (OS/USB) ---
from .platform import (
    USBDevice,
    _connected_usb_devices,
    _system_vendor,
    is_linux,
    is_windows,
    system,
)

# --- detection ---
from .detect import _plugin_matches_detect, detect_hardware

# --- commands ---
from .commands import _build_plugin_command, get_command

# Backward compat: keep hardware.__file__ pointing to original hardware.py
# location so tests computing G213 path via dirname(hardware.__file__) still work.
__file__ = os.path.normpath(
    os.path.join(os.path.dirname(__file__), '..', 'hardware.py')
)

__all__ = [
    # constants / registry
    'hardware',
    '_core_detect',
    '_plugin_hardware',
    '_plugin_detect',
    '_get_plugin_detect',
    '_SYSTEM_VENDOR_PATHS',
    'register_plugin_hardware',
    'clear_plugin_hardware',
    'get_all_hardware',
    'get_all_hardware_names',
    'is_plugin_hardware',
    # core
    '_g213_script',
    '_resolve_core_command',
    '_find_core_plugins_dirs',
    '_load_core_hardware',
    # platform
    'is_windows',
    'is_linux',
    'USBDevice',
    '_connected_usb_devices',
    '_system_vendor',
    'system',
    # detection
    '_plugin_matches_detect',
    'detect_hardware',
    # commands
    '_build_plugin_command',
    'get_command',
]
