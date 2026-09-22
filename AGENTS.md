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
  - `spotify/`: Spotify WebSocket integration (modular package)
    - `constants.py`: URLs, scopes, defaults, `_UNAUTHORIZED` sentinel
    - `session.py`: pooled `requests.Session` (`_get_session`)
    - `callback.py`: OAuth callback HTTP server (`_CallbackHandler`, `_run_local_server`)
    - `auth.py`: token & OAuth flow (`get_spotify_token`, `build_auth_url`, `exchange_code_for_token`, `refresh_access_token`, `save_spotify_tokens`, `ensure_valid_token`, `check_spotify_api_available`)
    - `parsing.py`: Dealer/REST payload parsers (`_extract_track_from_payload`, `_parse_ws_message`, `_extract_track_and_art_from_ws_raw`)
    - `api.py`: one-shot REST fetches (`_fetch_track_sync`, `_fetch_current_playback_sync`)
    - `watcher.py`: push watcher (`_build_websocket_url`, `watch_spotify_websocket`, `watch_spotify_api`)
    - `__init__.py`: public facade re-exporting flat `beatboard.spotify` API for backward compat
  - `playerctl.py`: `playerctl` backend + `process_art_url` pipeline
  - `hardware.py`: hardware registry & detection
  - `config.py` / `globs.py` / `logs.py` / `args.py`
  - `cache/`: SQLite cache, `plugins/`: YAML drivers, `G213Colors/`: vendor driver
- `tests/`: Unit tests, `docs/`: Docs
- `pyproject.toml`: Config, `.github/`: CI/templates

## rules

- ignore `__pycache__`, `build`, `dist`, `venv`, `src/beatboard/G213Colors/**`

No Cursor or Copilot rules found.
