# Changelog

All notable changes to this project will be documented in this file.

## [0.3.0] - 2026-09-24

### 🚀 Features

- Modular plugin system with core drivers and configurable plugin_dir
- *(agents)* Enforce modular dev style via rule, agent and CI check
- Add doctor diagnostics and apply ruff formatting
- Add ARGB-optimized color selection for LED lighting
- Add g502 SE HERO plugin via ratbagctl, move openrgb to examples

### 🐛 Bug Fixes

- Resolve CI syntax error and add cross-platform documentation
- Hardware detection, debug and color handling
- *(plugins)* Make ~/.config/beatboard/plugins extensions actually run
- Apply {color} placeholder substitution to core hardware commands

### 🚜 Refactor

- *(spotify)* Split monolithic spotify.py into modular package
- Fix all remaining modularity violations
- Make all version references dynamic from pyproject.toml
- Remove Spotify environment variable support
- Make doctor diagnostics dynamic based on detected hardware
- Remove all legacy fallbacks and hardcoded hardware

### 📚 Documentation

- Update README, AGENTS and guides for modular spotify package
- Sync project structure for full modularity refactor
- Sync README and hardware docs with YAML-driven hardware system

### 🧪 Testing

- Update tests and add plugin documentation

## [0.2.0] - 2026-09-21

### 🚀 Features

- Implement Spotify-style color extraction with performance optimization
- *(hardware)* Add automatic detection
- *(hardware)* Move hardware list from config to cache db and add --refresh-hardware
- Add --api flag for Spotify API support
- *(logs)* Add color coding to debug logs
- *(logs)* Add separators between each song

### 🐛 Bug Fixes

- *(color)* Handle missing sklearn in kmeans_colors fallback
- *(cache, spotify)* Deduplicate cache logs and add track fast-path
- *(spotify)* Eliminate ws head-of-line blocking and broaden Dealer art URL extraction
- Testing

### 🚜 Refactor

- *(logs)* Make debug logs minimal and human readable

### 📚 Documentation

- *(legal)* Clarify node-vibrant as inspiration not adaptation

### ⚡ Performance

- *(cache,spotify)* Fast track_id cache path and 401 auto-refresh

### 🎨 Styling

- Apply ruff formatting

### ⚙️ Miscellaneous Tasks

- Update GitHub Actions to Node 24-compatible versions
- Git-ignore

## [0.1.3] - 2026-05-31

### 🚀 Features

- *(hardware)* Asusctl support
- Add caching system  ([#15](https://github.com/abdellatif-temsamani/BeatBoard/issues/15))
- *(cli)* Add version to help menu and short argument forms

### 🐛 Bug Fixes

- Add missing about fields to issue templates
- *(cache)* Name must contain only alphanumeric, underscores, hyphens
- Logging color
- Test

### 🚜 Refactor

- Split debug flag into separate command and palette options
- *(cli)* [**breaking**] Change default mode from single to continuous
- *(debug)* Imporve palette debug
- *(cache)* Update db path

### 📚 Documentation

- Add docstrings to core functions and classes

### ⚙️ Miscellaneous Tasks

- Bump version to 0.1.2

## [0.1.1-3] - 2025-12-10

### ⚙️ Miscellaneous Tasks

- Update publish workflow and bump version
- Bump version

## [0.1.1-2] - 2025-12-09

### ⚙️ Miscellaneous Tasks

- Bump version

## [0.1.1-1] - 2025-12-09

### 📚 Documentation

- Update development installation and usage instructions

### 🎨 Styling

- *(print)* Unified messages

### ⚙️ Miscellaneous Tasks

- Update packaging and linting configuration for G213Colors submodule
- Bump version

## [0.1.1] - 2025-12-09

### 🚀 Features

- *(hardware)* Add support for Razer devices
- *(cli)* Rename main.py to beatboard and make executable, update documentation
- Add Spotify availability check and improve hardware argument validation

### 🐛 Bug Fixes

- Test import
- Update G213 hardware command to use sys.executable and dynamic path
- Add command existence check to prevent execution errors

### 🚜 Refactor

- *(args)* Extract hardware keys variable and improve help text formatting
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

- *(publish)* Fix awk command
- Add development tools and fix README install command
- Optimize publish workflow for efficiency

### 🛡️ Security

- Version to 0.1.1

## [0.1.0-5] - 2025-12-09

### ⚙️ Miscellaneous Tasks

- *(publish)* Simplify changelog extraction to single section and add GITHUB_TOKEN env
- *(publish)* Fix awk command

## [0.1.0-4] - 2025-12-09

### 💼 Other

- *(version)* Bump version to 0.1.0-3
- Bump version to 0.1.0-4

### 📚 Documentation

- *(readme)* Update installation command to use editable install with dev dependencies

### ⚙️ Miscellaneous Tasks

- Add contents write permission to release job
- Update publish workflow to use changelog for release notes
- Skip changelog header in release notes extraction
- Enhance publish workflow with proper quoting and permissions
- *(publish)* Fix changelog extraction regex and add debug output
- *(publish)* Improve release notes extraction and changelog formatting

## [0.1.0-2] - 2025-12-09

### 🚀 Features

- Require Python 3.11+ for contourpy compatibility
- Add console script entry point for beatboard command
- Update dependencies for Python 3.8+ support
- *(config)* Add OpenCode AI configuration for development tools
- *(cli)* Add --version flag and switch to static versioning
- *(test)* Add pytest-asyncio for automatic async test support

### 🐛 Bug Fixes

- Update dependencies for Python 3.8-3.10 compatibility
- Correct relative links in CONTRIBUTING.md to point to root README.md
- Update license to SPDX expression in pyproject.toml
- Update dependencies for security, improve async handling, and fix docs
- Plt run on the main thread
- Prevent matplotlib crashes when empty palettes are passed to debug_palette
- *(commit-writer)* Correct wording in commit writer description

### 💼 Other

- *(opencode)* Add bash permissions and update commit-writer prompt
- Bump version to 0.1.0-1
- *(deps)* Migrate from requirements.txt to pyproject.toml
- *(version)* Bump version to 0.1.0-2

### 🚜 Refactor

- Backport code to Python 3.8+ syntax
- Change imports to relative imports within src package

### 📚 Documentation

- Add AGENTS.md with coding guidelines for AI agents
- Fix spelling and grammar in CHANGELOG.md
- Update contributing guide and CI workflow
- Update docs and CI for Python 3.8+ support

### 🎨 Styling

- Format src/_version.py with ruff

### ⚙️ Miscellaneous Tasks

- Use python -m pytest in CI workflow
- Add pip caching to speed up CI runs
- *(workflows)* Add publish workflow and enable reusable CI
- *(workflows)* Update GitHub release action to v2
- *(config)* Add CodeRabbit configuration to exclude CHANGELOG.md from reviews
- Update workflow to use pyproject.toml for caching and dev dependencies

### ◀️ Revert

- Restore Python 3.11+ requirement

## [0.1.0] - 2025-12-06

### 🚀 Features

- Debug tool
- Follow spotify
- Seperators
- Hardware selector
- *(hardware)* Added multiple hardware support args
- Pretty print
- *(args parser)* Better help menu
- Add comprehensive test suite, linting, and CI

### 🐛 Bug Fixes

- Color selection
- Duplicated var
- Permissions
- Specify the player in playerctl

### 🚜 Refactor

- *(core)* Better code structure
- *(follow mode)* Better follow
- *(playerctl)* Better command handling
- *(core)* Improve structure and cleanup across modules

### 📚 Documentation

- *(core)* Added doc strings
- *(playerctl)* Improved docs
- *(core)* Improved doc strings
- *(core)* Update and clarify module documentation
- *(README)* Improve read me
- Update changelog for v0.1.0

### ⚙️ Miscellaneous Tasks

- Gitinore
- Docs
- Open source data
- *(issue)* Create issue template
- *(repo)* Getting ready for opensource

<!-- generated by git-cliff -->
