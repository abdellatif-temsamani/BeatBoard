import os
import sys
from collections.abc import Callable
from types import SimpleNamespace

import pytest

from beatboard import hardware
from beatboard.hardware import detect_hardware, get_command

_g213_script = os.path.join(
    os.path.dirname(hardware.__file__), "G213Colors", "G213Colors.py"
)


@pytest.mark.parametrize(
    "hardware, color, expected",
    [
        (
            ["g213"],
            "ff0000",
            [[sys.executable, _g213_script, "-c", "ff0000"]],
        ),
        (
            ["g213"],
            "00ff00",
            [[sys.executable, _g213_script, "-c", "00ff00"]],
        ),
        (
            ["g213", "g213", "razer"],
            "000000",
            [
                [sys.executable, _g213_script, "-c", "000000"],
                [sys.executable, _g213_script, "-c", "000000"],
                ["razer-cli", "-c", "000000"],
            ],
        ),
        (
            ["razer"],
            "55ff99",
            [["razer-cli", "-c", "55ff99"]],
        ),
    ],
)
def test_get_command_valid(hardware, color, expected):
    commands = get_command(hardware, color)
    assert commands == expected


def test_get_command_invalid():
    with pytest.raises(ValueError, match="Unknown hardware"):
        get_command(["invalid"], "000000")  # type: ignore


def test_get_command_empty_hardware():
    commands = get_command([], "ffffff")
    assert commands == []


def make_executable_finder(*names: str) -> Callable[[str], str | None]:
    installed = set(names)
    return lambda name: f"/usr/bin/{name}" if name in installed else None


def test_detect_hardware_finds_connected_g213() -> None:
    devices = [SimpleNamespace(idVendor=0x046D, idProduct=0xC336)]

    detected = detect_hardware(devices=devices, system_vendor="Generic")

    assert detected == ["g213"]


def test_detect_hardware_requires_razer_cli_for_razer_devices() -> None:
    devices = [SimpleNamespace(idVendor=0x1532, idProduct=0x0221)]

    detected = detect_hardware(
        devices=devices,
        executable_finder=make_executable_finder(),
        system_vendor="Generic",
    )

    assert detected == []


def test_detect_hardware_finds_all_controllable_hardware() -> None:
    devices = [
        SimpleNamespace(idVendor=0x046D, idProduct=0xC336),
        SimpleNamespace(idVendor=0x1532, idProduct=0x0221),
        SimpleNamespace(idVendor=0x0B05, idProduct=0x19AF),
    ]

    detected = detect_hardware(
        devices=devices,
        executable_finder=make_executable_finder("razer-cli", "asusctl"),
        system_vendor="Generic",
    )

    assert detected == ["g213", "razer", "asus"]


def test_detect_hardware_finds_asus_system_without_usb_device() -> None:
    detected = detect_hardware(
        devices=[],
        executable_finder=make_executable_finder("asusctl"),
        system_vendor="ASUSTeK COMPUTER INC.",
    )

    assert detected == ["asus"]
