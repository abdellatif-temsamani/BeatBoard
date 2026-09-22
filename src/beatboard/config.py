from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import get_args

import yaml

from .globs import DebugCategory


class ConfigError(ValueError):
    """Raised when the user configuration is invalid."""


DEFAULT_CACHE_PATH_RAW = "~/.local/state/beatboard/cache.db"
DEFAULT_PLUGIN_DIR_RAW = "~/.config/beatboard/plugins"

DEFAULT_CONFIG: dict[str, object] = {
    "debug": [],
    "cache_path": DEFAULT_CACHE_PATH_RAW,
    "plugin_dir": DEFAULT_PLUGIN_DIR_RAW,
    "spotify_token": None,
    "spotify_refresh_token": None,
    "spotify_client_id": None,
    "spotify_client_secret": None,
    "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
    "spotify_websocket_url": "wss://dealer.spotify.com/?access_token={token}",
}


def _default_config_dict() -> dict[str, object]:
    """Return a fresh copy of the default config dictionary."""
    return {
        "cache_path": DEFAULT_CACHE_PATH_RAW,
        "plugin_dir": DEFAULT_PLUGIN_DIR_RAW,
        "debug": [],
        "spotify_token": None,
        "spotify_refresh_token": None,
        "spotify_client_id": None,
        "spotify_client_secret": None,
        "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
        "spotify_websocket_url": "wss://dealer.spotify.com/?access_token={token}",
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
    plugin_dir: str | None = DEFAULT_PLUGIN_DIR_RAW
    spotify_token: str | None = None
    spotify_refresh_token: str | None = None
    spotify_client_id: str | None = None
    spotify_client_secret: str | None = None
    spotify_redirect_uri: str = "http://127.0.0.1:8888/callback"
    spotify_websocket_url: str = "wss://dealer.spotify.com/?access_token={token}"


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

    if "plugin_dir" not in data:
        plugin_dir = str(Path(DEFAULT_PLUGIN_DIR_RAW).expanduser())
    else:
        raw_plugin_dir = data.get("plugin_dir")
        if raw_plugin_dir is None:
            plugin_dir = None
        elif isinstance(raw_plugin_dir, str):
            # Allow empty string to disable plugins; otherwise expand user
            if raw_plugin_dir.strip() == "":
                plugin_dir = None
            else:
                plugin_dir = str(Path(raw_plugin_dir).expanduser())
        else:
            raise ConfigError("plugin_dir must be a string or null")

    valid_debug = set(get_args(DebugCategory))
    for category in debug:
        if category not in valid_debug:
            raise ConfigError(f"unknown debug category '{category}'")

    # Spotify configuration – defaults match abdellatif dev app
    raw_spotify_token = data.get("spotify_token")
    if raw_spotify_token is not None and not isinstance(raw_spotify_token, str):
        raise ConfigError("spotify_token must be a string or null")
    spotify_token = raw_spotify_token

    raw_refresh = data.get("spotify_refresh_token")
    if raw_refresh is not None and not isinstance(raw_refresh, str):
        raise ConfigError("spotify_refresh_token must be a string or null")
    spotify_refresh_token = raw_refresh

    raw_client_id = data.get("spotify_client_id")
    if raw_client_id is not None and not isinstance(raw_client_id, str):
        raise ConfigError("spotify_client_id must be a string or null")
    spotify_client_id = raw_client_id

    raw_client_secret = data.get("spotify_client_secret")
    if raw_client_secret is not None and not isinstance(raw_client_secret, str):
        raise ConfigError("spotify_client_secret must be a string or null")
    spotify_client_secret = raw_client_secret

    raw_redirect = data.get("spotify_redirect_uri", "http://127.0.0.1:8888/callback")
    if raw_redirect is not None and not isinstance(raw_redirect, str):
        raise ConfigError("spotify_redirect_uri must be a string or null")
    spotify_redirect_uri = raw_redirect or "http://127.0.0.1:8888/callback"

    raw_ws_url = data.get(
        "spotify_websocket_url", "wss://dealer.spotify.com/?access_token={token}"
    )
    if raw_ws_url is not None and not isinstance(raw_ws_url, str):
        raise ConfigError("spotify_websocket_url must be a string or null")
    if isinstance(raw_ws_url, str) and raw_ws_url.strip():
        spotify_websocket_url = raw_ws_url.strip()
    else:
        spotify_websocket_url = "wss://dealer.spotify.com/?access_token={token}"

    # Auto-create missing default keys on disk so the user config stays up-to-date.
    missing_keys = [k for k in DEFAULT_CONFIG if k not in data]
    if missing_keys:
        healed = dict(data)
        for key in missing_keys:
            healed[key] = DEFAULT_CONFIG[key]
        # Preserve any extra user keys, just add missing defaults; write sorted.
        _write_default_config(path, defaults=healed)

    return Config(
        debug=debug,  # type: ignore[arg-type]
        cache_path=cache_path,
        plugin_dir=plugin_dir,
        spotify_token=spotify_token,
        spotify_refresh_token=spotify_refresh_token,
        spotify_client_id=spotify_client_id,
        spotify_client_secret=spotify_client_secret,
        spotify_redirect_uri=spotify_redirect_uri,
        spotify_websocket_url=spotify_websocket_url,
    )
