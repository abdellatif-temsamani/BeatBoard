"""Central version handling – single source of truth is ``pyproject.toml``.

This module is the single place that knows how to obtain the BeatBoard
version. All other modules must import ``__version__`` from here instead
of hard-coding a string or calling ``importlib.metadata.version`` directly.

Resolution order:
  1. Parse ``pyproject.toml`` via ``tomllib`` / regex fallback (source checkout)
  2. ``importlib.metadata.version`` (installed distribution)
  3. ``"0.0.0"`` ultimate fallback.

File is checked first so edits to ``pyproject.toml`` are reflected
without reinstalling when running from a source checkout; installed
packages without a nearby ``pyproject.toml`` fall back to metadata.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:  # pragma: no cover - Python <3.8 fallback
    from importlib_metadata import PackageNotFoundError, version  # type: ignore[no-redef,import-not-found]


def _read_version_from_pyproject() -> str | None:
    """Try to read ``project.version`` from the nearest ``pyproject.toml``."""
    try:
        # pyproject.toml is at the repository root: <root>/pyproject.toml
        # This file lives at <root>/src/beatboard/_version.py -> parents[2] == <root>
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        if not pyproject.is_file():
            # Fallback: walk upwards (covers editable installs with different layout)
            for parent in Path(__file__).resolve().parents:
                candidate = parent / "pyproject.toml"
                if candidate.is_file():
                    pyproject = candidate
                    break
            else:
                return None

        # Prefer tomllib (accurate, handles edge cases)
        try:
            import tomllib  # Python 3.11+

            with pyproject.open("rb") as f:
                data = tomllib.load(f)
            v = data.get("project", {}).get("version")
            if isinstance(v, str) and v.strip():
                return v.strip()
        except Exception:
            pass

        # Regex fallback – works even when tomllib is unavailable or file is minimal
        text = pyproject.read_text(encoding="utf-8")
        m = re.search(r'^\s*version\s*=\s*["\']([^"\']+)["\']', text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    except Exception:
        pass
    return None


def _get_version() -> str:
    # Prefer pyproject.toml when running from source checkout
    file_version = _read_version_from_pyproject()
    if file_version:
        return file_version
    for dist_name in ("BeatBoard", "beatboard"):
        try:
            return version(dist_name)
        except PackageNotFoundError:
            continue
        except Exception:
            continue
    return "0.0.0"


__version__ = _get_version()

__all__ = ["__version__"]
