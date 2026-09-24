# BeatBoard 🎵💡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Cross-platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey.svg)](https://www.linux.org/)

BeatBoard is a CLI tool that dynamically changes your keyboard's RGB lighting
based on the colors extracted from the album art of the currently playing
Spotify song. On Linux, it uses `playerctl` to fetch metadata. On Windows (and
Linux), it can use the Spotify WebSocket API for real-time track change
notifications, applying vibrant colors to create an immersive music experience.
Hardware is **YAML-driven** – built-ins live in `src/beatboard/core_plugins/*.yaml`
and community drivers are drop-in files in `~/.config/beatboard/plugins/` (see
`docs/plugins.md` and `docs/hardware.md`).

## ✨ Features

- 🎨 **Automatic color extraction** from album art of currently playing tracks
- 🌈 **Vibrant color analysis** to find dominant and complementary colors
- ⌨️ **Real-time RGB keyboard control** with smooth transitions
- 🔄 **Continuous following mode** for live color updates as songs change
- 🎵 **Spotify Desktop integration** through `playerctl` (Linux) or Spotify
  WebSocket API (cross-platform)
- 🎯 **Hardware-agnostic, YAML-driven design** – add a device with a `.yaml` manifest, no code
- 🔌 **Plugin ecosystem** – community drivers in `~/.config/beatboard/plugins/` (OpenRGB, Corsair, Hue, etc.)
- 💾 **Intelligent caching** system for improved performance (SQLite + LRU)
- 🔌 **Automatic hardware detection** when `--hardware` is omitted (cached, `--refresh-hardware` to re-detect)
- 🩺 **`beatboard --doctor` diagnostics** – Spotify, permissions, hardware, OpenRGB, cache, config
- 🪟 **Cross-platform support** - works on Linux and Windows (macOS via `--api` + manual hardware)

## 📋 Requirements

### System Requirements

- **Linux or Windows operating system** (Linux: tested on Ubuntu, Fedora, Arch; Windows: 10/11)
- **Python 3.11 or higher**
- **Spotify Desktop** (required)
- No GUI plotting stack required (palette debug output is terminal-based)

### Platform-Specific Requirements

**Linux (built-ins, all optional – auto-detected via USB + executable):**
- **`playerctl`** for media player integration (default method)
- **`razer-cli` + `razer-daemon` (OpenRazer)** for Razer devices – vendor `1532` + executable
- **`asusctl`** for Asus devices – vendor `0B05` **or** DMI `asus` + executable
- **`ratbagctl` (libratbag)** for Logitech G502 SE HERO – `046d:c08b` + executable
- **`openrgb`** for generic OpenRGB devices – executable-only (community plugin in `examples/plugins/openrgb.yaml`)

Community drivers (Corsair K70 via `ck-corsair-cli`, Hue Bridge, etc.) declare their
own `executables`/`usb`/`system_vendor` in `~/.config/beatboard/plugins/*.yaml` – see `docs/plugins.md`.
Direct USB for G213 (`046d:c336`) needs `pyusb` and `input` group membership.

**When using `--api` flag (any platform):**
- **Spotify API access** via `--api` flag (required on platforms without `playerctl`)
- Spotify Developer credentials (client ID and secret) for OAuth authentication
- Hardware tools above are still used if available on `$PATH` (Razer/Asus/G502/OpenRGB via plugins)

### Media Players

- **Spotify Desktop** (required)

## 🚀 Installation

### Quick Install

```bash
pip install beatboard
```

### Alternative: Using pipx

For isolated installation without affecting system Python:

```bash
pipx install beatboard
```

### Verify Installation

```bash
# Test basic functionality
beatboard --help

# Linux: Verify playerctl integration (should show current player status)
playerctl status

# Diagnostics (checks Spotify, permissions, hardware, plugins, cache)
beatboard --doctor

# Test hardware access (shows expanded commands without changing hardware)
beatboard --debug command --once
beatboard --debug plugins --once   # plugin loading
beatboard --debug all --once       # + USB/DMI/executable detection
```

## Spotify API Setup

### Spotify API Configuration

Use the Spotify API when `playerctl` is not available on your platform, or if you prefer the WebSocket API. This works on any platform (Linux/Mac/Windows). Follow these steps:

1. **Create a Spotify Developer App:**
   - Go to [https://developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
   - Log in with your Spotify account
   - Click "Create App"
   - Fill in the required fields (app name, description)
   - Set the redirect URI to: `http://127.0.0.1:8888/callback`
   - Save your **Client ID** and **Client Secret**

2. **Configure BeatBoard:**
   Create or edit the config file at `~/.config/beatboard/config.yaml` (Linux) or `%USERPROFILE%\.config\beatboard\config.yaml` (Windows):

    ```yaml
    spotify_client_id: "your_client_id_here"
    spotify_client_secret: "your_client_secret_here"
    spotify_redirect_uri: "http://127.0.0.1:8888/callback"
    # plugin_dir: "~/.config/beatboard/plugins"  # default, null to disable
    # cache_path: "~/.local/state/beatboard/cache.db"
    # debug: []
    ```

3. **Run BeatBoard:**
   ```bash
   beatboard --api
   ```

   The first run will open a browser window for OAuth authentication. After
   authorizing, the access token will be saved to your config file for future use.

### Hardware Support by Platform

**Linux (auto-detected):**
- **Logitech G213** – direct USB `046d:c336` (no executable)
- **Razer devices** – `1532` + `razer-cli`
- **Asus devices** – `0B05` **or** DMI `asus` + `asusctl`
- **Logitech G502 SE HERO** – `046d:c08b` + `ratbagctl`
- **OpenRGB / Corsair / Hue** – community YAML plugins (`~/.config/beatboard/plugins/`), e.g. `openrgb` (executable-only)

**macOS:**
- Hardware support depends on macOS-compatible CLI tools
- **Razer/Asus/G502:** Requires macOS-compatible `razer-cli`/`asusctl`/`ratbagctl` (if available) – on macOS/Windows detection is executable-only (`g213` never auto-detects)
- **Generic:** OpenRGB if available, otherwise manufacturer software + manual `--hardware`
- **Spotify:** `--api` required (`playerctl` is Linux-only)

**Windows:**
- Same executable-only detection as macOS
- **Razer/Asus/G502:** Requires Windows-compatible CLI tools if available
- **Logitech G213:** PyUSB script is Linux-only – use G Hub or OpenRGB wrapper
- **Generic:** OpenRGB (`examples/plugins/openrgb.yaml` → `~/.config/beatboard/plugins/`)
- **Spotify:** `--api` required

If your hardware tool is not available on your platform, specify hardware manually
with `--hardware <name>` or add a YAML plugin pointing at the available CLI (see `docs/hardware.md` and `docs/plugins.md`).

## 🎮 Usage

### Platform Selection

**Linux (default):** Uses `playerctl` for Spotify integration
```bash
beatboard
```

**Any platform (Linux/Mac/Windows):** Uses Spotify WebSocket API
```bash
beatboard --api
```

**Note:** On Windows and macOS, `playerctl` is not available, so `--api` is required. On Linux, you can choose either method.

### Single Color Change

Extract colors from the current song and apply once:

**Linux (playerctl):**
```bash
beatboard --once
```

**Any platform (Spotify API):**
```bash
beatboard --api --once
```

### Continuous Mode

Follow the playing song and update colors in real-time:

**Linux (playerctl):**
```bash
beatboard
```

**Any platform (Spotify API):**
```bash
beatboard --api
```

Press `Ctrl+C` to stop following.

### Advanced Options

```bash
# Specify hardware (built-ins + community plugins from ~/.config/beatboard/plugins/)
beatboard --hardware g213
beatboard --hardware g213 razer asus g502 openrgb
beatboard --hardware corsair-k70 --once   # community driver

# Or omit --hardware to auto-detect (Linux: USB+exe+DMI; Windows: exe-only; cached)
beatboard
beatboard --refresh-hardware   # force re-detection and update cache
beatboard --reset-cache        # clear color cache (keeps hardware cache)

# Use Spotify API (required on Windows/macOS, optional on Linux)
beatboard --api

# Debug mode – categories: command, palette, cache, perf, api, plugins, all
beatboard --debug command --once
beatboard --debug plugins --once
beatboard --debug all --once

# Diagnostics
beatboard --doctor

# Show version / help
beatboard --version
beatboard --help   # lists available hardware (builtin vs plugin)
```

**Plugin quick start:**

```bash
mkdir -p ~/.config/beatboard/plugins
cp examples/plugins/openrgb.yaml ~/.config/beatboard/plugins/
cp examples/plugins/corsair-k70.yaml ~/.config/beatboard/plugins/
beatboard --hardware openrgb --once --debug command
beatboard --debug plugins --once
```

See `docs/plugins.md` for the full YAML schema (`command` with `{color}`/`{hex}`, `detect: usb`/`executables`/`system_vendor`).

## 🛠️ Development

For development, clone the repository and use the dev script to run the latest
code:

```bash
# Install in development mode
pip install -e ".[dev]"

# Verify dependencies are healthy
python -m pytest

# Run with dev script
python beatboard_dev.py --help
python beatboard_dev.py
python beatboard_dev.py --once --debug all
```

## 🏗️ Architecture

```
src/beatboard/
├── __init__.py          # beatboard_main() – CLI + plugin load + hardware cache + mode dispatch
├── color/               # palette extraction (was color_gen.py 640L)
│   ├── constants.py     # RGB/_SIG_BITS, COLOR_CACHE_VERSION
│   ├── models.py        # Swatch, VibrantPalette
│   ├── quantize.py      # Histogram/VBox/MMCQ
│   ├── palette.py       # generator
│   ├── image.py         # extract_palette / get_color_palette
│   └── __init__.py      # facade
├── spotify/             # WebSocket (Dealer) – pure push, no polling
│   ├── constants.py / session.py / callback.py / parsing.py / api.py (leaves)
│   ├── oauth.py / tokens.py / flow.py + auth.py facade (auth lifecycle)
│   ├── watcher/ (connection.py, hydration.py, handlers.py, core.py, api.py) + __init__.py facade
│   └── __init__.py      # public facade (beatboard.spotify flat API)
├── hardware/            # YAML-driven registry + detection
│   ├── constants.py     # _SYSTEM_VENDOR_PATHS (leaf, no deps)
│   ├── registry.py      # hardware dict + _core_detect/_plugin_* + register/clear/get_all_hardware
│   ├── core.py          # load YAML core_plugins → hardware (_g213_script, _resolve_core_command, _load_core_hardware)
│   ├── platform.py      # is_windows/is_linux, USB/DMI (_connected_usb_devices, _system_vendor, USBDevice)
│   ├── detect.py        # detect_hardware() + _plugin_matches_detect() – exe+usb+vendor, Windows exe-only
│   ├── commands.py      # get_command() + _build_plugin_command() – {color}/{hex} expansion
│   └── __init__.py      # facade – flat beatboard.hardware API (backward compat)
├── core_plugins/        # built-in YAML manifests (g213, razer, asus, g502) – source of truth for hardware
├── playerctl/           # playerctl backend
│   ├── session.py       # pooled Session (_get_image_session)
│   ├── keys.py          # create_cache_key / create_track_cache_key
│   ├── player.py        # playerctl() / check_spotify_available
│   ├── image.py         # get_image
│   ├── apply.py         # _run_hardware / apply_colors (asyncio subprocess)
│   ├── process.py       # process_art_url (cache → palette → hardware)
│   ├── watcher.py       # watch_playerctl
│   └── __init__.py      # facade
├── cache/               # SQLite + memory
│   ├── memory.py        # LRU (_mem_by_name/track)
│   ├── compression.py   # compress/decompress
│   ├── store.py         # cache_colors / get_cached_colors*
│   ├── db.py            # _has_track_id_column, migrations, get/set_cached_hardware
│   └── colors.py        # facade
├── plugins/             # YAML driver engine
│   ├── loader.py        # discover/load/register plugins (DEFAULT_PLUGIN_DIR, get_plugin_dir)
│   ├── models.py        # Plugin, HardwareSpec, DetectSpec, UsbId, validate_plugin_dict
│   ├── registry.py      # extension_registry
│   ├── hooks.py / errors.py
│   └── __init__.py      # facade
├── doctor/              # diagnostics (config, cache, permissions, hardware, spotify, openrgb, system)
├── config.py / globs.py / logs.py / args.py / utils.py (35-line shim)
└── G213Colors/          # vendor driver (submodule, src/beatboard/G213Colors/G213Colors.py)
```

All former god files (`color_gen.py` 640L, `spotify.py` 1992L, `hardware.py` 439L, `playerctl.py` 401L, `cache/colors.py` 411L, `watcher.py` 726L) were split by single responsibility into packages with `__init__.py` facades – flat imports like `from beatboard.spotify import watch_spotify_api` and `from beatboard.color import Swatch` stay import-compatible. Built-in hardware is now declarative YAML in `core_plugins/` loaded by `hardware/core.py: _load_core_hardware()`.

## 🖥️ Supported Hardware

### Currently Supported (built-ins, auto-detected)

- **Logitech G213 Prodigy** – `046d:c336`, direct USB HID (`src/beatboard/G213Colors/G213Colors.py`), single region
- **Razer devices** – vendor `1532` + `razer-cli` (OpenRazer), e.g. BlackWidow/DeathAdder/Mamba
- **Asus devices** – `0B05` **or** DMI `asus` + `asusctl` (ROG/TUF Aura)
- **Logitech G502 SE HERO** – `046d:c08b` + `ratbagctl` (libratbag) – both LEDs via `sh -c` template

All built-ins are defined in `src/beatboard/core_plugins/*.yaml` and use the
`{color}`/`{hex}` command template (see `docs/hardware.md` for `detect` semantics and Windows exe-only behavior).

### Community Plugins (no code, drop-in YAML)

BeatBoard loads `~/.config/beatboard/plugins/*.yaml` at startup (`config.plugin_dir`, `null` to disable).
Examples in `examples/plugins/`:

- **OpenRGB generic** – `openrgb` executable-only (`openrgb.yaml`) – many motherboards/RAM/keyboards
- **Corsair K70** – `ck-corsair-cli` via `corsair-k70.yaml` (`1b1c:1b49` + executable)
- **Hue Bridge**, **notify-extension** (hook: `track_change`/`color_applied`)

Any CLI that accepts a hex color can be wrapped: `["my-tool", "-c", "{color}"]` → `my-tool -c ff0000` (or placeholder inside arg). See `docs/plugins.md` for the full schema and `docs/hardware.md` for platform notes.

### Adding Support

- **Community driver (recommended):** copy an example from `examples/plugins/`, set `name`/`command`/`detect`, drop in `~/.config/beatboard/plugins/`, `beatboard --debug plugins --once` – no fork required.
- **Built-in:** add a YAML to `src/beatboard/core_plugins/` and open a PR (uses `__python__`/`__g213_script__` placeholders via `hardware/core.py: _resolve_core_command`).

_Want to publish yours? Open a PR adding it to `examples/plugins/` – see `docs/hardware.md: Contributing Hardware Support`._

## 🤝 Contributing

We welcome contributions of all kinds! Here's how you can help:

### Code Contributions

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Hardware Support

Help us expand hardware compatibility by:

- Adding YAML drivers (community plugins) – see `docs/plugins.md` and `docs/hardware.md`
- Testing on new hardware and sharing `lsusb`/`beatboard --doctor` output
- Documentation improvements

See our [Contributing Guide](.github/CONTRIBUTING.md) and `docs/hardware.md` for detailed guidelines.

## 🐛 Troubleshooting

### Common Issues

**Linux:**
- **"playerctl not found"**:
  - Ubuntu/Debian: `sudo apt install playerctl`
  - Fedora: `sudo dnf install playerctl`
  - Arch Linux: `sudo pacman -S playerctl`
- **"Permission denied" / "USB device not found"** (G213):
  - `sudo usermod -a -G input $USER` → re-login, then `beatboard --doctor` (Permissions check)
  - Test direct: `python src/beatboard/G213Colors/G213Colors.py -c ff0000`

**When using `--api` flag (any platform):**
- **"Spotify API authentication failed"**:
  - Verify your client ID and secret are correct in `~/.config/beatboard/config.yaml`
  - Ensure the redirect URI matches: `http://127.0.0.1:8888/callback`
  - Check that your Spotify Developer app has the correct scopes
- **"No Spotify token found"**:
  - Run `beatboard --api` to trigger OAuth authentication
  - Check that port 8888 is not blocked by your firewall
  - Verify the callback URL is accessible

**Hardware detection (Linux vs Windows):**
- **Linux:** auto-detection needs USB **and** executable (Asus needs `0B05` **or** DMI `asus` + `asusctl`); check `beatboard --debug all --once` → `detect: usb_ids=… vendor='…' razer-cli=…`
- **Windows:** detection is **executable-only** (`g213` never auto-detects, USB/DMI ignored) – use `--hardware <name> --api` or ensure the tool is on `$PATH`
- **"Hardware not detected"**: Use `--hardware` flag manually, check `beatboard --help` (shows `builtin` vs `plugin`), or `beatboard --debug plugins --once` for YAML warnings
- **Plugin not loaded**: duplicate `name`, reserved name (`g213`/`razer`/`asus`/`g502`), or invalid YAML → skipped with yellow warning, see `docs/plugins.md: Validation & errors`

**Cross-platform:**
- **"No album art"**: Ensure current Spotify Desktop song has album art available
- **Cache / detection**: `beatboard --refresh-hardware` forces re-detection; `beatboard --reset-cache` clears color cache; SQLite cache is at `~/.local/state/beatboard/cache.db` (`config.cache_path`)

### Getting Help

- Run diagnostics first: `beatboard --doctor`
- See our [Support Guide](SUPPORT.md) for help channels
- Open an [issue](https://github.com/abdellatif-temsamani/BeatBoard/issues)
- Join our discussions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.

## 🙏 Acknowledgments

- The `playerctl` team for media player integration (Linux)
- Spotify for the WebSocket API enabling cross-platform support
- Logitech for the G213 hardware specifications
- Contributors and beta testers

## 📊 Project Status

![GitHub issues](https://img.shields.io/github/issues/abdellatif-temsamani/BeatBoard)
![GitHub pull requests](https://img.shields.io/github/issues-pr/abdellatif-temsamani/BeatBoard)

---

**Made with ❤️ by the BeatBoard team**
