from typing import Literal

hardware: dict[str, list[str]] = {
    "g213": [
        "python",
        "./G213Colors/G213Colors.py",
        "-c",
    ],
}

hardwareName = Literal["g213"]  # ← keyof, fully auto


def get_command(names: list[hardwareName], color: str) -> list[list[str]]:
    """Get the command to run the hardware.

    Args:
        names: The names of the hardware to change the color of.
        color: The color to change the hardware to.

    Returns:
        list[list[str]]: The command to run the hardware.
    """

    commands: list[list[str]] = []
    for name in names:
        if name in hardware:
            commands.append(hardware[name] + [color])
        else:
            raise ValueError(f"Unknown hardware: {name}")
    return commands
