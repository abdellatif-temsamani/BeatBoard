# BeatBoard 🎵💡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Linux](https://img.shields.io/badge/platform-linux-lightgrey.svg)](https://www.linux.org/)

BeatBoard is a CLI tool for Linux that dynamically changes your keyboard's RGB
lighting based on the colors extracted from the album art of the currently
playing Spotify Desktop song. It uses `playerctl` to fetch metadata and applies
vibrant colors to create an immersive music experience.

## ✨ Features

- 🎨 **Automatic color extraction** from album art of currently playing tracks
- 🌈 **Vibrant color analysis** to find dominant and complementary colors
- ⌨️ **Real-time RGB keyboard control** with smooth transitions
- 🔄 **Continuous following mode** for live color updates as songs change
- 🎵 **Spotify Desktop integration** through `playerctl` for seamless music
  control
- 🎯 **Hardware-agnostic design** for easy expansion to new devices

## 📋 Requirements

### System Requirements

- **Linux operating system** (tested on Ubuntu, Fedora, Arch)
- **Python 3.11 or higher**
- **`playerctl`** for media player integration

### optional Requirements

- **`razer-cli`** for Razer device support (optional)
- **`asusctl`** for Asus device support (optional)

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

# Verify playerctl integration (should show current player status)
playerctl status

# Test hardware access (may require sudo for initial setup)
beatboard --debug
```

## 🎮 Usage

### Single Color Change

Extract colors from the current song and apply once:

```bash
beatboard
```

### Continuous Mode

Follow the playing song and update colors in real-time:

```bash
beatboard --follow
```

Press `Ctrl+C` to stop following.

### Advanced Options

```bash
# Specify hardware
beatboard --hardware g213

# Debug mode
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

# Run with dev script
python beatboard_dev.py --help
python beatboard_dev.py
python beatboard_dev.py --follow
```

## 🖥️ Supported Hardware

### Currently Supported

- **Logitech G213 Prodigy** - single region supported
- **Razer devices** - via razer-cli (optional, requires razer-cli installation)

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

- **"playerctl not found"**:
  - Ubuntu/Debian: `sudo apt install playerctl`
  - Fedora: `sudo dnf install playerctl`
  - Arch Linux: `sudo pacman -S playerctl`
- **"Permission denied"**: Add user to `input` group:
  `sudo usermod -a -G input $USER`
- **"No album art"**: Ensure current Spotify Desktop song has album art
  available

### Getting Help

- See our [Support Guide](SUPPORT.md) for help channels
- Open an [issue](https://github.com/abdellatif-temsamani/BeatBoard/issues)
- Join our discussions

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file
for details.

## 🙏 Acknowledgments

- The `playerctl` team for media player integration
- Logitech for the G213 hardware specifications
- Contributors and beta testers

## 📊 Project Status

![GitHub issues](https://img.shields.io/github/issues/abdellatif-temsamani/BeatBoard)
![GitHub pull requests](https://img.shields.io/github/issues-pr/abdellatif-temsamani/BeatBoard)

---

**Made with ❤️ by the BeatBoard team**
