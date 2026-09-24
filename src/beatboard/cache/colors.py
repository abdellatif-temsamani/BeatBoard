"""Color cache facade – backward-compatible public API.

Split into submodules for modularity (AGENTS.md: single responsibility):

- :mod:`beatboard.cache.memory` – in-memory LRU
- :mod:`beatboard.cache.compression` – json+zlib+base64
- :mod:`beatboard.cache.store` – DB persistence (orchestrator)
- :mod:`beatboard.cache.db` – ``_has_track_id_column`` helper

This file preserves ``from beatboard.cache.colors import ...`` imports used by
``playerctl`` and external callers while keeping the module under the
soft 400-line limit (now ~50 lines, orchestrator via re-exports).
"""

from __future__ import annotations

from .compression import compress_colors, decompress_colors
from .db import _has_track_id_column, get_connection
from .memory import (
    _MAX_MEM,
    _mem_by_name,
    _mem_by_track,
    _mem_order,
    _mem_get_name,
    _mem_get_track,
    _mem_put,
    clear_memory_cache,
)
from .store import (
    cache_colors,
    cache_colors_by_track_id,
    get_cached_colors,
    get_cached_colors_by_track_id,
)

__all__ = [
    '_MAX_MEM',
    '_has_track_id_column',
    '_mem_by_name',
    '_mem_by_track',
    '_mem_get_name',
    '_mem_get_track',
    '_mem_order',
    '_mem_put',
    'cache_colors',
    'cache_colors_by_track_id',
    'clear_memory_cache',
    'compress_colors',
    'decompress_colors',
    'get_cached_colors',
    'get_cached_colors_by_track_id',
    'get_connection',
]
