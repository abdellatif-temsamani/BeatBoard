"""Hardware registry – single source for mutable hardware state."""

from __future__ import annotations

# Core hardware is now defined in ./core_plugins/*.yaml and src/beatboard/core_plugins/*.yaml
# This dict is populated at import time from those YAML files.
hardware: dict[str, list[str]] = {}

# Core + plugin-provided hardware (populated at runtime)
_core_detect: dict[str, object] = {}  # DetectSpec for core hardware
_plugin_hardware: dict[str, list[str]] = {}
_plugin_detect: dict[str, object] = {}  # DetectSpec stored as opaque for detection


def _get_plugin_detect(name: str):
    return _plugin_detect.get(name)


def register_plugin_hardware(
    name: str,
    command: list[str],
    detect: object | None = None,
) -> None:
    """Register a community plugin hardware driver.

    Args:
        name: Unique plugin hardware name (slug).
        command: Command template (list[str]), may contain ``{color}`` placeholder.
        detect: Optional DetectSpec from plugin models.

    Raises:
        ValueError: If name conflicts with built-in or already registered plugin.
    """
    if name in hardware:
        raise ValueError(f"plugin hardware name '{name}' conflicts with built-in")
    if name in _plugin_hardware:
        raise ValueError(f"plugin hardware name '{name}' already registered")
    if not command or not all(isinstance(c, str) and c for c in command):
        raise ValueError('command must be non-empty list of strings')
    _plugin_hardware[name] = list(command)
    if detect is not None:
        _plugin_detect[name] = detect


def clear_plugin_hardware() -> None:
    """Clear all plugin hardware registrations (for tests)."""
    _plugin_hardware.clear()
    _plugin_detect.clear()


def get_all_hardware() -> dict[str, list[str]]:
    """Return combined built-in + plugin hardware registry."""
    return {**hardware, **_plugin_hardware}


def get_all_hardware_names() -> list[str]:
    """Return sorted list of all available hardware names (built-in + plugins)."""
    return sorted(get_all_hardware().keys())


def is_plugin_hardware(name: str) -> bool:
    return name in _plugin_hardware
