from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

import yaml

from .globs import DebugCategory


class ConfigError(ValueError):
    """Raised when the user configuration is invalid."""


DEFAULT_CACHE_PATH_RAW = "~/.local/state/beatboard/cache.db"

DEFAULT_CONFIG: dict[str, object] = {
    "debug": [],
    "cache_path": DEFAULT_CACHE_PATH_RAW,
}


def _default_config_dict() -> dict[str, object]:
    """Return a fresh copy of the default config dictionary."""
    return {
        "cache_path": DEFAULT_CACHE_PATH_RAW,
        "debug": [],
    }


def _write_default_config(
    path: Path, *, defaults: dict[str, object] | None = None
) -> None:
    """Write default config values to ``path``, creating parents as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = defaults if defaults is not None else _default_config_dict()
    path.write_text(yaml.safe_dump(data, sort_keys=True), encoding="utf-8")


@dataclass(slots=True)
class Config:
    """User-configurable BeatBoard settings."""

    debug: list[DebugCategory] = field(default_factory=list)
    cache_path: str | None = DEFAULT_CACHE_PATH_RAW


def get_config_path() -> Path:
    """Return the path to BeatBoard's user configuration file."""
    return Path.home() / ".config" / "beatboard" / "config.yaml"


def load_config(path: Path) -> Config:
    """Create the default config when needed and load it from ``path``."""
    if not path.exists():
        _write_default_config(path)

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML: {exc}") from exc

    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError("top level must be a mapping")

    debug = data.get("debug", [])
    if not isinstance(debug, list) or not all(isinstance(item, str) for item in debug):
        raise ConfigError("debug must be a list of strings")

    if "cache_path" not in data:
        cache_path = str(Path(DEFAULT_CACHE_PATH_RAW).expanduser())
    else:
        raw_cache_path = data.get("cache_path")
        if raw_cache_path is None:
            cache_path = None
        elif isinstance(raw_cache_path, str):
            cache_path = str(Path(raw_cache_path).expanduser())
        else:
            raise ConfigError("cache_path must be a string or null")

    valid_debug = set(get_args(DebugCategory))
    for category in debug:
        if category not in valid_debug:
            raise ConfigError(f"unknown debug category '{category}'")

    # Auto-create missing default keys on disk so the user config stays up-to-date.
    # Also remove legacy hardware key if present (moved to cache db).
    missing_keys = [k for k in DEFAULT_CONFIG if k not in data]
    has_legacy_hardware = "hardware" in data
    if missing_keys or has_legacy_hardware:
        healed = dict(data)
        for key in missing_keys:
            healed[key] = DEFAULT_CONFIG[key]
        if has_legacy_hardware:
            healed.pop("hardware", None)
        # Preserve any extra user keys, just add missing defaults; write sorted.
        _write_default_config(path, defaults=healed)

    return Config(
        debug=debug,  # type: ignore[arg-type]
        cache_path=cache_path,
    )
