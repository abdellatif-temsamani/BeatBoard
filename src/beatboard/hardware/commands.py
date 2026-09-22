"""Hardware command building."""

from __future__ import annotations

from .registry import _plugin_hardware, get_all_hardware, hardware


def _build_plugin_command(template: list[str], color: str) -> list[str]:
    """Build plugin command, handling {color} placeholder."""
    has_placeholder = any("{color}" in part for part in template)
    if has_placeholder:
        built = [
            part.replace("{color}", color).replace("{hex}", color) for part in template
        ]
        return built
    return template + [color]


def get_command(names: list[str], color: str) -> list[list[str]]:
    """Get the command to run the hardware.

    Args:
        names: The names of the hardware to change the color of (built-in or plugin).
        color: The color to change the hardware to (hex without '#', e.g. 'ff0000').

    Returns:
        list[list[str]]: The command to run the hardware.
    """
    if not isinstance(color, str) or len(color) != 6:
        pass

    commands: list[list[str]] = []
    combined = get_all_hardware()
    for name in names:
        if name in combined:
            if name in _plugin_hardware:
                commands.append(_build_plugin_command(_plugin_hardware[name], color))
            else:
                commands.append(_build_plugin_command(hardware[name], color))
        else:
            raise ValueError(f"Unknown hardware: {name}")
    return commands
