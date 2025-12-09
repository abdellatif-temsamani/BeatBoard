import os
import sys
import pytest

from beatboard import hardware
from beatboard.hardware import get_command

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
