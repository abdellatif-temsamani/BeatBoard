"""In-memory LRU cache for color palettes (hot path).

Avoids 1ms SQLite round-trip on WebSocket pushes by keeping recent
palettes in process memory. Bounded to ``_MAX_MEM`` entries with a simple
FIFO eviction – cheap and good enough for the cache workload.
"""

from __future__ import annotations

from typing import Dict, List, Optional

_MAX_MEM = 512
_mem_by_name: Dict[str, List[str]] = {}
_mem_by_track: Dict[str, List[str]] = {}
_mem_order: List[str] = []


def _mem_get_name(name: str) -> Optional[List[str]]:
    return _mem_by_name.get(name)


def _mem_get_track(track_id: str) -> Optional[List[str]]:
    return _mem_by_track.get(track_id)


def _mem_put(
    name: Optional[str], colors: List[str], track_id: Optional[str] = None
) -> None:
    if name:
        _mem_by_name[name] = colors
        _mem_order.append(f"n:{name}")
    if track_id:
        _mem_by_track[track_id] = colors
        _mem_order.append(f"t:{track_id}")
        legacy = f"track_{track_id}"
        _mem_by_name[legacy] = colors
    while len(_mem_order) > _MAX_MEM * 2:
        oldest = _mem_order.pop(0)
        if oldest.startswith("n:"):
            k = oldest[2:]
            _mem_by_name.pop(k, None)
        else:
            k = oldest[2:]
            _mem_by_track.pop(k, None)


def clear_memory_cache() -> None:
    """Clear in-memory caches (useful for tests)."""
    _mem_by_name.clear()
    _mem_by_track.clear()
    _mem_order.clear()
