from pathlib import Path

import yaml

import pytest

from beatboard.config import ConfigError, get_config_path, load_config


def test_load_config_creates_default_file(tmp_path: Path) -> None:
    config_path = tmp_path / "beatboard" / "config.yaml"

    config = load_config(config_path)

    assert config_path.is_file()
    assert yaml.safe_load(config_path.read_text(encoding="utf-8")) == {
        "cache_path": "~/.local/state/beatboard/cache.db",
        "debug": [],
        "plugin_dir": "~/.config/beatboard/plugins",
        "spotify_client_id": None,
        "spotify_client_secret": None,
        "spotify_redirect_uri": "http://127.0.0.1:8888/callback",
        "spotify_refresh_token": None,
        "spotify_token": None,
        "spotify_websocket_url": "wss://dealer.spotify.com/?access_token={token}",
    }
    assert config.debug == []
    assert config.cache_path == str(
        Path.home() / ".local" / "state" / "beatboard" / "cache.db"
    )
    assert config.spotify_token is None
    assert config.spotify_refresh_token is None
    assert config.spotify_client_id is None
    assert config.spotify_client_secret is None
    assert config.spotify_redirect_uri == "http://127.0.0.1:8888/callback"
    assert (
        config.spotify_websocket_url == "wss://dealer.spotify.com/?access_token={token}"
    )
    # pure websocket mode – poll_interval is legacy and not in default config
    assert (
        not hasattr(config, "spotify_poll_interval")
        or getattr(config, "spotify_poll_interval", None) is None
        or "spotify_poll_interval"
        not in yaml.safe_load(config_path.read_text(encoding="utf-8"))
    )
    # hardware is no longer stored in config - should not be present
    assert not hasattr(config, "hardware")
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "hardware" not in raw
    assert "spotify_poll_interval" not in raw


def test_get_config_path_uses_home_config_directory(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))

    assert get_config_path() == tmp_path / ".config" / "beatboard" / "config.yaml"


def test_load_config_reads_user_settings(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "debug:\n  - cache\ncache_path: /tmp/beatboard.db\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.debug == ["cache"]
    assert config.cache_path == "/tmp/beatboard.db"


def test_load_config_ignores_legacy_hardware(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "hardware:\n  - g213\ndebug:\n  - cache\ncache_path: /tmp/beatboard.db\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    # hardware key should be removed from file and not present in Config
    assert not hasattr(config, "hardware")
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    assert "hardware" not in data
    assert data["debug"] == ["cache"]
    assert data["cache_path"] == "/tmp/beatboard.db"


def test_load_config_rejects_unknown_debug_category(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("debug:\n  - noisy\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="unknown debug category 'noisy'"):
        load_config(config_path)


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        ("- g213\n", "top level must be a mapping"),
        ("debug: cache\n", "debug must be a list of strings"),
        ("cache_path: []\n", "cache_path must be a string or null"),
        ("hardware: [\n", "invalid YAML"),
    ],
)
def test_load_config_rejects_invalid_shapes(
    tmp_path: Path, contents: str, message: str
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(contents, encoding="utf-8")

    with pytest.raises(ConfigError, match=message):
        load_config(config_path)
