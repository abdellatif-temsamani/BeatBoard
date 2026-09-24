from __future__ import annotations

from .models import Plugin

# Global extension plugin registry (name -> Plugin)
extension_registry: dict[str, Plugin] = {}


def get_extension_plugins() -> dict[str, Plugin]:
    return dict(extension_registry)


def clear_extension_registry() -> None:
    extension_registry.clear()
