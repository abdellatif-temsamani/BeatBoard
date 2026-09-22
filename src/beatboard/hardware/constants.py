"""Hardware constants – leaf module with no dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

hardwareName = Literal["g213", "razer", "asus"]

_SYSTEM_VENDOR_PATHS = (
    Path("/sys/class/dmi/id/sys_vendor"),
    Path("/sys/devices/virtual/dmi/id/sys_vendor"),
)
