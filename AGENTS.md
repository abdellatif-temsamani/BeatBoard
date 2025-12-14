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

- `src/`: Package, `tests/`: Unit tests, `docs/`: Docs
- `pyproject.toml`: Config, `.github/`: CI/templates

## rules

- ignore `__pycache__`, `build`, `dist`, `venv`, `src/beatboard/G213Colors/**`

No Cursor or Copilot rules found.
