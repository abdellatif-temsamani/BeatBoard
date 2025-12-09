# Changelog

All notable changes to this project will be documented in this file.

## [0.1.1-3] - 2025-12-09

### ⚙️ Miscellaneous Tasks

- Update publish workflow and bump version
- Bump version

## [0.1.1-2] - 2025-12-09

### 📚 Documentation

- Update development installation and usage instructions

### 🎨 Styling

- _(print)_ Unified messages

### ⚙️ Miscellaneous Tasks

- Update packaging and linting configuration for G213Colors submodule
- Bump version

## [0.1.1] - 2025-12-09

### 🚀 Features

- _(hardware)_ Add support for Razer devices
- _(cli)_ Rename main.py to beatboard and make executable, update documentation
- Add Spotify availability check and improve hardware argument validation

### 🐛 Bug Fixes

- Test import
- Update G213 hardware command to use sys.executable and dynamic path
- Add command existence check to prevent execution errors

### 🚜 Refactor

- _(args)_ Extract hardware keys variable and improve help text formatting
- Reorganize project structure into beatboard package
- Move G213Colors submodule to src/beatboard/
- Improve error handling in art processing

### 📚 Documentation

- Fix install deps command quotes
- Update installation and development documentation
- Add hardware documentation and improve README

### 🎨 Styling

- Format warning message with rich colors
- Condense AGENTS.md formatting and content

### ⚙️ Miscellaneous Tasks

- _(publish)_ Simplify changelog extraction to single section and add
  GITHUB_TOKEN env
- _(publish)_ Fix awk command
- Add development tools and fix README install command
- Optimize publish workflow for efficiency

### 🛡️ Security

- Version to 0.1.1

## [0.1.0-4] - 2025-12-09

### 💼 Other

- _(version)_ Bump version to 0.1.0-3
- Bump version to 0.1.0-4

### 📚 Documentation

- _(readme)_ Update installation command to use editable install with dev
  dependencies

### ⚙️ Miscellaneous Tasks

- Add contents write permission to release job
- Update publish workflow to use changelog for release notes
- Skip changelog header in release notes extraction
- Enhance publish workflow with proper quoting and permissions
- _(publish)_ Fix changelog extraction regex and add debug output
- _(publish)_ Improve release notes extraction and changelog formatting

## [0.1.0-2] - 2025-12-09

### 🚀 Features

- Require Python 3.11+ for contourpy compatibility
- Add console script entry point for beatboard command
- Update dependencies for Python 3.8+ support
- _(config)_ Add OpenCode AI configuration for development tools
- _(cli)_ Add --version flag and switch to static versioning
- _(test)_ Add pytest-asyncio for automatic async test support

### 🐛 Bug Fixes

- Update dependencies for Python 3.8-3.10 compatibility
- Correct relative links in CONTRIBUTING.md to point to root README.md
- Update license to SPDX expression in pyproject.toml
- Update dependencies for security, improve async handling, and fix docs
- Plt run on the main thread
- Prevent matplotlib crashes when empty palettes are passed to debug_palette
- _(commit-writer)_ Correct wording in commit writer description

### 💼 Other

- _(opencode)_ Add bash permissions and update commit-writer prompt
- Bump version to 0.1.0-1
- _(deps)_ Migrate from requirements.txt to pyproject.toml
- _(version)_ Bump version to 0.1.0-2

### 🚜 Refactor

- Backport code to Python 3.8+ syntax
- Change imports to relative imports within src package

### 📚 Documentation

- Add AGENTS.md with coding guidelines for AI agents
- Fix spelling and grammar in CHANGELOG.md
- Update contributing guide and CI workflow
- Update docs and CI for Python 3.8+ support

### 🎨 Styling

- Format src/\_version.py with ruff

### ⚙️ Miscellaneous Tasks

- Use python -m pytest in CI workflow
- Add pip caching to speed up CI runs
- _(workflows)_ Add publish workflow and enable reusable CI
- _(workflows)_ Update GitHub release action to v2
- _(config)_ Add CodeRabbit configuration to exclude CHANGELOG.md from reviews
- Update workflow to use pyproject.toml for caching and dev dependencies

### ◀️ Revert

- Restore Python 3.11+ requirement

## [0.1.0] - 2025-12-06

### 🚀 Features

- Debug tool
- Follow spotify
- Seperators
- Hardware selector
- _(hardware)_ Added multiple hardware support args
- Pretty print
- _(args parser)_ Better help menu
- Add comprehensive test suite, linting, and CI

### 🐛 Bug Fixes

- Color selection
- Duplicated var
- Permissions
- Specify the player in playerctl

### 🚜 Refactor

- _(core)_ Better code structure
- _(follow mode)_ Better follow
- _(playerctl)_ Better command handling
- _(core)_ Improve structure and cleanup across modules

### 📚 Documentation

- _(core)_ Added doc strings
- _(playerctl)_ Improved docs
- _(core)_ Improved doc strings
- _(core)_ Update and clarify module documentation
- _(README)_ Improve read me
- Update changelog for v0.1.0

### ⚙️ Miscellaneous Tasks

- Gitinore
- Docs
- Open source data
- _(issue)_ Create issue template
- _(repo)_ Getting ready for opensource

<!-- generated by git-cliff -->
