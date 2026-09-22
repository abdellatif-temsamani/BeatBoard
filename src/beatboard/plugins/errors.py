from __future__ import annotations


class PluginError(ValueError):
    """Base error for plugin loading / validation."""


class PluginValidationError(PluginError):
    """Raised when a plugin manifest is invalid."""

    def __init__(self, plugin_file: str, message: str) -> None:
        super().__init__(f"{plugin_file}: {message}")
        self.plugin_file = plugin_file
        self.message = message
