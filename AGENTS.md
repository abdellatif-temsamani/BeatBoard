# AGENTS.md - Coding Guidelines for BeatBoard

## Commands
- **Install deps**: `pip install -r requirements.txt`
- **Run all tests**: `python -m pytest`
- **Run single test**: `python -m pytest tests/test_file.py::test_function`
- **Lint**: `ruff check .`
- **Format**: `ruff format .`
- **Type check**: `mypy src/` (if installed)
- **Build**: `python -m build` (requires build package)

## Code Style
- **Python version**: 3.8+
- **Formatting**: ruff (88 char lines, single quotes preferred)
- **Linting**: ruff with custom select/ignore rules, ignore submodules
- **Imports**: stdlib, third-party, local; sorted with ruff
- **Naming**: snake_case functions/vars, PascalCase classes, UPPER_CASE constants
- **Types**: Use type hints; `from __future__ import annotations` for py3.11+
- **Error handling**: Specific exceptions; avoid bare except
- **Async**: Use asyncio; mark async tests with @pytest.mark.asyncio
- **Docstrings**: Google/NumPy style for functions/classes
- **Commits**: don't commit unless i tell you, use conventional commit
- **Tests**: pytest; fixtures for setup; mock external deps

## Project Structure
- `src/`: Main package
- `tests/`: Unit tests
- `main.py`: Entry point
- `pyproject.toml`: Config (deps, tools)
- `.github/`: CI, templates

No Cursor or Copilot rules found.
