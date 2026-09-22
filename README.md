# BeatBoard 🎵💡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Cross-platform](https://img.shields.io/badge/platform-linux%20%7C%20windows-lightgrey.svg)](https://www.linux.org/)

BeatBoard is a CLI tool that dynamically changes your keyboard's RGB lighting
based on the colors extracted from the album art of the currently playing
Spotify song. On Linux, it uses `playerctl` to fetch metadata. On Windows (and
Linux), it can use the Spotify WebSocket API for real-time track change
notifications, applying vibrant colors to create an immersive music experience.

## ✨ Features

- 🎨 **Automatic color extraction** from album art of currently playing tracks
- 🌈 **Vibrant color analysis** to find dominant and complementary colors
- ⌨️ **Real-time RGB keyboard control** with smooth transitions
- 🔄 **Continuous following mode** for live color updates as songs change
- 🎵 **Spotify Desktop integration** through `playerctl` (Linux) or Spotify
  WebSocket API (cross-platform)
- 🎯 **Hardware-agnostic design** for easy expansion to new devices
- 💾 **Intelligent caching** system for improved performance
- 🔌 **Automatic hardware detection** when `--hardware` is omitted
- 🪟 **Cross-platform support** - works on Linux and Windows

## 📋 Requirements

### System Requirements

- **Linux or Windows operating system** (Linux: tested on Ubuntu, Fedora, Arch; Windows: 10/11)
- **Python 3.11 or higher**
- **Spotify Desktop** (required)
- No GUI plotting stack required (palette debug output is terminal-based)

### Platform-Specific Requirements

**Linux:**
- **`playerctl`** for media player integration (default method)
- **`razer-cli`** for Razer device support (optional)
- **`asusctl`** for Asus device support (optional)

**When using `--api` flag (any platform):**
- **Spotify API access** via `--api` flag (required on platforms without `playerctl`)
- Spotify Developer credentials (client ID and secret) for OAuth authentication
- **`razer-cli`** for Razer device support (optional, if available)
- **`asusctl`** for Asus device support (optional, if available)

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

# Test hardware access (may require sudo for initial setup on Linux)
beatboard --debug
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
   Create or edit the config file at `%USERPROFILE%\.config\beatboard\config.yaml`:

   ```yaml
   spotify_client_id: "your_client_id_here"
   spotify_client_secret: "your_client_secret_here"
   spotify_redirect_uri: "http://127.0.0.1:8888/callback"
   ```

   Or set environment variables:
   ```powershell
   setx SPOTIFY_CLIENT_ID "your_client_id_here"
   setx SPOTIFY_CLIENT_SECRET "your_client_secret_here"
   ```

3. **Run BeatBoard:**
   ```bash
   beatboard --api
   ```

   The first run will open a browser window for OAuth authentication. After
   authorizing, the access token will be saved to your config file for future use.

### Hardware Support by Platform

**Linux:**
- **Razer devices:** Requires `razer-cli` (optional)
- **Asus devices:** Requires `asusctl` (optional)
- **Logitech G213:** Direct USB control supported

**macOS:**
- Hardware support depends on the availability of macOS-compatible CLI tools
- **Razer devices:** Requires macOS-compatible `razer-cli` (if available)
- **Asus devices:** Requires macOS-compatible `asusctl` (if available)
- **Logitech G213:** May require alternative control methods on macOS

**Windows:**
- Hardware support depends on the availability of Windows-compatible CLI tools
- **Razer devices:** Requires Windows-compatible `razer-cli` (if available)
- **Asus devices:** Requires Windows-compatible `asusctl` (if available)
- **Logitech G213:** May require alternative control methods on Windows

If your hardware tool is not available on your platform, you may need to specify hardware manually or use alternative RGB control software.

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
# Specify hardware
beatboard --hardware g213

# Or omit --hardware to detect supported connected devices automatically
beatboard

# Use Spotify API (required on Windows, optional on Linux)
beatboard --api

# Debug mode (optional categories: command, palette, cache, api)
beatboard --debug

# Show version
beatboard --version
```

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
python beatboard_dev.py --follow
```

## 🏗️ Architecture

```
src/beatboard/
├── __init__.py          # beatboard_main() – CLI + hardware + mode dispatch
├── color/               # palette extraction (was color_gen.py 640L)
│   ├── constants.py     # RGB/_SIG_BITS, COLOR_CACHE_VERSION
│   ├── models.py        # Swatch, VibrantPalette
│   ├── quantize.py      # Histogram/VBox/MMCQ
│   ├── palette.py       # generator
│   ├── image.py         # extract_palette / get_color_palette
│   └── __init__.py      # facade; color_gen.py is deprecated shim
├── spotify/             # WebSocket (Dealer) – pure push, no polling
│   ├── constants.py / session.py / callback.py / parsing.py / api.py (leaves)
│   ├── oauth.py / tokens.py / flow.py + auth.py facade (auth lifecycle)
│   ├── watcher/ (connection.py, hydration.py, handlers.py, core.py, api.py) + __init__.py facade
│   └── __init__.py      # public facade (beatboard.spotify flat API)
├── hardware/            # registry + detection
│   ├── registry.py      # hardware dict + Literal + register/clear
│   ├── core.py          # load YAML core_plugins → hardware
│   ├── platform.py      # is_windows/is_linux, USB/DMI
│   ├── detect.py        # detect_hardware (+ plugin matching)
│   ├── commands.py      # get_command
│   └── __init__.py      # facade
├── playerctl/           # playerctl backend
│   ├── session.py       # pooled Session (_get_image_session)
│   ├── keys.py          # create_cache_key / create_track_cache_key
│   ├── player.py        # playerctl() / check_spotify_available
│   ├── image.py         # get_image
│   ├── apply.py         # _run_hardware / apply_colors
│   ├── process.py       # process_art_url (cache → palette → hardware)
│   ├── watcher.py       # watch_playerctl
│   └── __init__.py      # facade
├── cache/               # SQLite + memory
│   ├── memory.py        # LRU (_mem_by_name/track)
│   ├── compression.py   # compress/decompress
│   ├── store.py         # cache_colors / get_cached_colors*
│   ├── db.py            # _has_track_id_column, migrations
│   └── colors.py        # facade
├── config.py / globs.py / logs.py / args.py / utils.py (35-line shim)
├── plugins/             # YAML drivers
└── G213Colors/          # vendor driver (submodule)
```

All former god files (`color_gen.py` 640L, `spotify.py` 1992L, `hardware.py` 439L, `playerctl.py` 401L, `cache/colors.py` 411L, `watcher.py` 726L) were split by single responsibility into packages with `__init__.py` facades – flat imports like `from beatboard.spotify import watch_spotify_api` and `from beatboard.color_gen import Swatch` stay import-compatible.

## 🖥️ Supported Hardware

### Currently Supported

- **Logitech G213 Prodigy** - single region supported
- **Razer devices** - via razer-cli (optional, requires razer-cli installation)
- **Asus devices** - via asusctl (optional, requires asusctl installation)

### Planned Support

- Corsair RGB keyboards
- Generic HID RGB devices

_Want to add support for your device? See our
[Contributing Guide](#contributing)!_

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

- Adding device drivers
- Testing on new hardware
- Documentation improvements

See our [Contributing Guide](.github/CONTRIBUTING.md) for detailed guidelines.

## 🐛 Troubleshooting

### Common Issues

**Linux:**
- **"playerctl not found"**:
  - Ubuntu/Debian: `sudo apt install playerctl`
  - Fedora: `sudo dnf install playerctl`
  - Arch Linux: `sudo pacman -S playerctl`
- **"Permission denied"**: Add user to `input` group:
  `sudo usermod -a -G input $USER`

**When using `--api` flag (any platform):**
- **"Spotify API authentication failed"**:
  - Verify your client ID and secret are correct in config.yaml
  - Ensure the redirect URI matches: `http://127.0.0.1:8888/callback`
  - Check that your Spotify Developer app has the correct scopes
- **"No Spotify token found"**:
  - Run `beatboard --api` to trigger OAuth authentication
  - Check that port 8888 is not blocked by your firewall
  - Verify the callback URL is accessible

**Cross-platform:**
- **"No album art"**: Ensure current Spotify Desktop song has album art available
- **"Hardware not detected"**: Use `--hardware` flag to specify your device manually
- **"No supported hardware detected"**: Connect a supported device or check hardware tool installation

### Getting Help

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
