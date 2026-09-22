#!/usr/bin/env python3
"""Enforce BeatBoard modularity rules. Fails CI if violated."""

from __future__ import annotations

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "beatboard"

SOFT = 400
HARD = 800
EXCLUDE = {"G213Colors", "__pycache__", "graphify-out"}
# Grandfathered large files – pass with SOFT warning only until refactored
GRANDFATHERED = {
    pathlib.Path("src/beatboard/spotify/watcher.py"),
    pathlib.Path("src/beatboard/color_gen.py"),
}

ALLOW_LARGE_RE = re.compile(r"#\s*modularity:\s*allow-large")

violations: list[str] = []
warnings: list[str] = []


def check_file(path: pathlib.Path) -> None:
    rel = path.relative_to(ROOT)
    if any(part in EXCLUDE for part in path.parts):
        return
    text = path.read_text(encoding="utf-8", errors="ignore")
    if ALLOW_LARGE_RE.search(text):
        return
    lines = len(text.splitlines())
    if lines > HARD:
        violations.append(
            f"HARD {rel}: {lines} lines > {HARD} – split into package with facade __init__.py"
        )
    elif lines > SOFT:
        # grandfathered files are warnings, not blocking
        if rel in GRANDFATHERED:
            warnings.append(
                f"SOFT {rel}: {lines} lines > {SOFT} – grandfathered, consider splitting"
            )
        else:
            warnings.append(f"SOFT {rel}: {lines} lines > {SOFT} – consider splitting")


def check_utils_dump() -> None:
    for p in SRC.rglob("utils.py"):
        if "G213Colors" in str(p):
            continue
        # existing 35-line utils.py is grandfathered; only flag if >100 lines
        try:
            if len(p.read_text(encoding="utf-8", errors="ignore").splitlines()) > 100:
                violations.append(
                    f"UTILS {p.relative_to(ROOT)}: utils.py dumping ground forbidden – use domain modules"
                )
            else:
                warnings.append(
                    f"NOTE {p.relative_to(ROOT)}: utils.py exists (35 lines) – avoid growing, prefer domain modules"
                )
        except Exception:
            violations.append(
                f"UTILS {p.relative_to(ROOT)}: utils.py dumping ground forbidden – use domain modules"
            )


def check_facade(path: pathlib.Path) -> None:
    # If a directory has __init__.py but no re-exports, warn
    if path.is_dir() and (path / "__init__.py").exists():
        init = (path / "__init__.py").read_text(encoding="utf-8", errors="ignore")
        if "from ." not in init and "import" not in init:
            # allow empty __init__ for cache etc
            pass


def main() -> int:
    for py in SRC.rglob("*.py"):
        check_file(py)
    check_utils_dump()
    if warnings:
        print("Modularity warnings (non-blocking):")
        for w in warnings:
            print(f"  - {w}")
    if violations:
        print("\nModularity check failed:")
        for v in violations:
            print(f"  - {v}")
        print("\nRef: AGENTS.md Modularity Rules, example: src/beatboard/spotify/")
        return 1
    print("\nModularity check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
