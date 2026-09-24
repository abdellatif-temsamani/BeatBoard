"""Compression helpers for color palettes.

Palettes are stored as JSON → zlib → base64 so SQLite ``TEXT`` column
stays compact while remaining portable across migrations.
"""

from __future__ import annotations

import base64
import json
import zlib
from typing import List


def compress_colors(colors: List[str]) -> str:
    """Compress a list of color strings into a base64-encoded string.

    Args:
        colors: List of color strings to compress.

    Returns:
        Base64-encoded compressed string.
    """
    raw = json.dumps(colors).encode('utf-8')
    compressed = zlib.compress(raw)
    return base64.b64encode(compressed).decode('utf-8')


def decompress_colors(data: str) -> List[str]:
    """Decompress a base64-encoded string back into a list of color strings.

    Args:
        data: Base64-encoded compressed string.

    Returns:
        List of decompressed color strings.
    """
    compressed = base64.b64decode(data)
    raw = zlib.decompress(compressed)
    return json.loads(raw.decode('utf-8'))
