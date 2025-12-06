from typing import Literal

__keyboards: dict[str, list[str]] = {
    "g213": ["python", "./G213Colors/G213Colors.py"],
}

KeyboardName = Literal["g213"]  # ← keyof, fully auto

def get_command(name: KeyboardName) -> list[str]:
    return __keyboards[name]
