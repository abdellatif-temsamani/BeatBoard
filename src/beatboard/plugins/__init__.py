"""BeatBoard plugins – modular hardware drivers and extensions.

Plugins are YAML manifests placed in ``~/.config/beatboard/plugins/`` (configurable via ``plugin_dir``).

Each file ``*.yaml`` / ``*.yml`` defines one plugin:

    name: my-driver
    version: "1.0.0"
    type: hardware
    hardware:
      command: ["my-cli", "-c"]   # ``{color}`` placeholder optional, otherwise appended
      detect:
        usb:
          - vendor: 0x1b1c
            product: 0x1b49
        executables: ["my-cli"]
        system_vendor: "MyVendor"

Or extension:

    name: my-extension
    type: extension
    extension:
      hooks:
        - event: track_change
          command: ["notify-send", "{title}"]

Public API:
    load_plugins(plugin_dir) -> (plugins, errors)
    register_plugins(plugins) -> (count, skipped)
    get_plugin_dir(config_value)
"""

from __future__ import annotations

from pathlib import Path

from .errors import PluginError, PluginValidationError
from .loader import (
    DEFAULT_PLUGIN_DIR,
    discover_plugin_files,
    get_plugin_dir,
    load_plugin_file,
    load_plugins,
    register_plugins,
)
from .models import DetectSpec, ExtensionSpec, HardwareSpec, HookSpec, Plugin, UsbId
from .hooks import run_extension_hooks
from .registry import (
    clear_extension_registry,
    extension_registry,
    get_extension_plugins,
)

__all__ = [
    'Plugin',
    'HardwareSpec',
    'DetectSpec',
    'UsbId',
    'ExtensionSpec',
    'HookSpec',
    'PluginError',
    'PluginValidationError',
    'load_plugins',
    'register_plugins',
    'load_plugin_file',
    'discover_plugin_files',
    'get_plugin_dir',
    'DEFAULT_PLUGIN_DIR',
    'extension_registry',
    'get_extension_plugins',
    'clear_extension_registry',
    'run_extension_hooks',
]


def get_default_plugin_dir() -> Path:
    """Return default plugin directory (``~/.config/beatboard/plugins``)."""
    return Path.home() / '.config' / 'beatboard' / 'plugins'
