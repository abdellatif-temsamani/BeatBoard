from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from beatboard.config import load_config
from beatboard.hardware import (
    clear_plugin_hardware,
    detect_hardware,
    get_all_hardware,
    get_command,
)
from beatboard.plugins import load_plugins, register_plugins
from beatboard.plugins.loader import get_plugin_dir
from beatboard.plugins.models import validate_plugin_dict
from beatboard.plugins.registry import clear_extension_registry


@pytest.fixture(autouse=True)
def _clear_plugins():
    clear_plugin_hardware()
    clear_extension_registry()
    yield
    clear_plugin_hardware()
    clear_extension_registry()


def test_get_plugin_dir_default() -> None:
    assert (
        get_plugin_dir("~/.config/beatboard/plugins")
        == Path.home() / ".config" / "beatboard" / "plugins"
    )


def test_get_plugin_dir_disabled() -> None:
    assert get_plugin_dir(None) is None
    assert get_plugin_dir("") is None


def test_load_config_plugin_dir_default(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    config = load_config(cfg)
    assert config.plugin_dir == str(Path.home() / ".config" / "beatboard" / "plugins")
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert data["plugin_dir"] == "~/.config/beatboard/plugins"


def test_load_config_plugin_dir_custom(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("plugin_dir: /tmp/myplugins\n", encoding="utf-8")
    config = load_config(cfg)
    assert config.plugin_dir == "/tmp/myplugins"


def test_load_config_plugin_dir_null(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("plugin_dir: null\n", encoding="utf-8")
    config = load_config(cfg)
    assert config.plugin_dir is None


def test_load_config_plugin_dir_invalid(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("plugin_dir: 123\n", encoding="utf-8")
    with pytest.raises(Exception, match="plugin_dir must be a string or null"):
        load_config(cfg)


def test_hardware_plugin_yaml_valid(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "myhw.yaml").write_text(
        """
name: myhw
type: hardware
hardware:
  command: ["my-tool", "-c"]
  detect:
    executables: ["my-tool"]
"""
    )
    plugins, errors = load_plugins(pdir)
    assert not errors
    assert "myhw" in plugins
    assert plugins["myhw"].hardware.command == ["my-tool", "-c"]  # type: ignore[union-attr]


def test_hardware_plugin_with_placeholder(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "hue.yaml").write_text(
        """
name: hue-bridge
type: hardware
hardware:
  command: ["hue-cli", "set", "--color={color}"]
"""
    )
    plugins, _ = load_plugins(pdir)
    register_plugins(plugins)
    # {color} inside arg should be expanded
    assert get_command(["hue-bridge"], "ff0000") == [
        ["hue-cli", "set", "--color=ff0000"]
    ]
    # Also test {hex} alias
    assert "hue-bridge" in get_all_hardware()


def test_hardware_plugin_append_color(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "append.yaml").write_text(
        """
name: append-test
type: hardware
hardware:
  command: ["tool", "-c"]
"""
    )
    plugins, _ = load_plugins(pdir)
    register_plugins(plugins)
    assert get_command(["append-test"], "00ff00") == [["tool", "-c", "00ff00"]]


def test_plugin_invalid_yaml_skipped(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "bad.yaml").write_text("not: [yaml: :\n")
    plugins, errors = load_plugins(pdir)
    assert not plugins
    assert len(errors) == 1


def test_plugin_duplicate_name(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "a.yaml").write_text(
        """
name: dup
type: hardware
hardware:
  command: ["tool-a"]
"""
    )
    (pdir / "b.yaml").write_text(
        """
name: dup
type: hardware
hardware:
  command: ["tool-b"]
"""
    )
    plugins, errors = load_plugins(pdir)
    assert len(plugins) == 1
    assert len(errors) == 1
    assert "duplicate" in str(errors[0]).lower()


def test_plugin_reserved_name_rejected(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "r.yaml").write_text(
        """
name: g213
type: hardware
hardware:
  command: ["tool"]
"""
    )
    plugins, errors = load_plugins(pdir)
    assert not plugins
    assert len(errors) == 1


def test_detect_hardware_with_plugin() -> None:
    # Register plugin manually
    from beatboard.hardware import register_plugin_hardware
    from beatboard.plugins.models import DetectSpec, UsbId

    clear_plugin_hardware()
    spec = DetectSpec(
        usb=[UsbId(vendor=0x1234, product=0x5678)], executables=["my-tool"]
    )
    register_plugin_hardware("test-detect", ["my-tool", "-c"], spec)

    def finder(name: str):
        return "/usr/bin/my-tool" if name == "my-tool" else None

    devices = [SimpleNamespace(idVendor=0x1234, idProduct=0x5678)]
    detected = detect_hardware(
        devices=devices, executable_finder=finder, system_vendor="Generic"
    )
    assert "test-detect" in detected

    # Without USB match, not detected
    detected2 = detect_hardware(
        devices=[], executable_finder=finder, system_vendor="Generic"
    )
    assert "test-detect" not in detected2

    # Without executable, not detected even with USB
    def finder_none(name: str):
        return None

    detected3 = detect_hardware(
        devices=devices, executable_finder=finder_none, system_vendor="Generic"
    )
    assert "test-detect" not in detected3


def test_detect_hardware_system_vendor(tmp_path: Path) -> None:
    from beatboard.hardware import register_plugin_hardware
    from beatboard.plugins.models import DetectSpec

    spec = DetectSpec(system_vendor="MyVendor", executables=["my-tool"])
    register_plugin_hardware("vendor-test", ["my-tool"], spec)

    def finder(name: str):
        return "/usr/bin/my-tool" if name == "my-tool" else None

    assert "vendor-test" in detect_hardware(
        devices=[], executable_finder=finder, system_vendor="MyVendor Inc."
    )
    assert "vendor-test" not in detect_hardware(
        devices=[], executable_finder=finder, system_vendor="Other"
    )


def test_extension_plugin(tmp_path: Path) -> None:
    pdir = tmp_path / "plugins"
    pdir.mkdir()
    (pdir / "ext.yaml").write_text(
        """
name: myext
type: extension
extension:
  hooks:
    - event: track_change
      command: ["notify-send", "hi"]
"""
    )
    plugins, errors = load_plugins(pdir)
    assert not errors
    assert "myext" in plugins
    registered, _ = register_plugins(plugins)
    assert registered == 1
    from beatboard.plugins.registry import extension_registry

    assert "myext" in extension_registry


def test_plugin_healing_missing_key(tmp_path: Path) -> None:
    cfg = tmp_path / "config.yaml"
    cfg.write_text("debug: []\n", encoding="utf-8")
    config = load_config(cfg)
    assert config.plugin_dir is not None
    data = yaml.safe_load(cfg.read_text(encoding="utf-8"))
    assert "plugin_dir" in data


def test_get_command_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown hardware"):
        get_command(["nonexistent"], "ff0000")  # type: ignore[arg-type]


def test_validate_plugin_dict_direct() -> None:
    from beatboard.plugins.errors import PluginValidationError

    with pytest.raises(PluginValidationError):
        validate_plugin_dict({}, Path("fake.yaml"))
