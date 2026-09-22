"""Hardware execution helper – alias to apply module for compatibility.

This shim exists to satisfy alternative naming (``hardware.py`` vs ``apply.py``)
mentioned in the refactor spec. The canonical implementation lives in
``apply.py``; this module re-exports the deduplicated helper and
``apply_colors``.
"""

from __future__ import annotations

from .apply import _run_hardware, apply_colors

__all__ = ["_run_hardware", "apply_colors"]
