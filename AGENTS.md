# AGENTS.md - Coding Guidelines for BeatBoard

## Commands

- Install deps: `pip install -e ".[dev]"`
- Run all tests: `python -m pytest`
- Run single test: `python -m pytest tests/test_file.py::test_function`
- Lint: `ruff check .`
- Format: `ruff format .`
- Type check: `mypy src/` (if installed)
- Build: `python -m build`
- Build and install globally: `./build_and_install.sh`

## Code Style

- Python: 3.11+, ruff formatting (88 chars, single quotes)
- Linting: ruff (ignore submodules)
- Imports: stdlib, third-party, local; auto-sorted
- Naming: snake_case funcs/vars, PascalCase classes, UPPER_CASE constants
- Types: Use hints; `from __future__ import annotations` for py3.11+
- Error handling: Specific exceptions; avoid bare except
- Async: asyncio; @pytest.mark.asyncio for tests
- Docstrings: Google/NumPy style
- Commits: Conventional commits only when instructed
- Tests: pytest with fixtures; mock external deps

## Project Structure

- `src/beatboard/`: Package
  - `color/`: palette extraction – `constants.py` (RGB/_SIG_BITS), `models.py` (Swatch/VibrantPalette), `quantize.py` (Histogram/VBox/MMCQ), `palette.py` (generator), `image.py` (`extract_palette`/`get_color_palette`)
  - `spotify/`: WebSocket integration (pure push)
    - `constants.py` / `session.py` / `callback.py` / `parsing.py` / `api.py` (leaves)
    - `oauth.py` / `tokens.py` / `flow.py` + `auth.py` facade (auth lifecycle)
    - `watcher/` (`connection.py`, `hydration.py`, `handlers.py`, `core.py`, `api.py`) + `__init__.py` facade
    - `__init__.py` public facade (`beatboard.spotify` flat API)
  - `hardware/`: registry + detection – `registry.py`, `core.py` (load YAML), `platform.py` (USB/DMI), `detect.py` (`detect_hardware`), `commands.py` (`get_command`)
  - `playerctl/`: playerctl backend – `session.py`, `keys.py`, `player.py` (`playerctl`/`check`), `image.py` (`get_image`), `apply.py`/`hardware.py` (hardware exec), `process.py` (`process_art_url`), `watcher.py` (`watch_playerctl`)
  - `cache/`: SQLite + memory – `memory.py` (LRU), `compression.py`, `store.py` (orchestrates), `db.py` (`_has_track_id_column`), `colors.py` facade
  - `config.py` / `globs.py` / `logs.py` / `args.py` / `utils.py` (35-line shim, don't grow)
  - `plugins/`: YAML drivers, `G213Colors/`: vendor driver
- `tests/`: Unit tests, `docs/`: Docs
- `pyproject.toml`: Config, `.github/`: CI/templates

## Modularity Rules (enforced)

- **Single responsibility**: one concern per file/module. If you describe a file with "and", split it.
- **File size**: soft limit 400 lines, hard limit 800. Files >400 lines should be justified; files >800 lines MUST be split into a package (`module/` with `__init__.py` facade). Exception requires ` # modularity: allow-large` comment with rationale.
- **Package over file**: when a module grows past 3 distinct responsibilities (e.g. auth + parsing + transport), extract cohesive submodules. Use a facade `__init__.py` that re-exports the flat public API for backward compat (see `src/beatboard/spotify/` as reference).
- **No god files**: no new `utils.py` dumping ground. Place code near its domain (`spotify/auth.py`, `hardware/registry.py`, etc.).
- **Public API**: keep `beatboard.<module>` import paths stable via facade re-exports; move implementation to submodules but never break `from beatboard.X import Y`.
- **Layering**: `constants.py` (no deps) → `session.py`/`parsing.py` (leaf) → `auth.py`/`api.py` (uses leaves) → `watcher.py` (orchestrates). Avoid circular imports; watcher imports leaves, never the reverse.
- **Check before commit**: run `python scripts/check_modularity.py` (or `ruff check . && python -m pytest`) – CI fails on violations.

## rules

- ignore `__pycache__`, `build`, `dist`, `venv`, `src/beatboard/G213Colors/**`, `graphify-out/**`

No Cursor or Copilot rules found.
