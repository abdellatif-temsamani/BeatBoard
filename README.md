# BeatBoard 🎵💡

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
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
- **Python 3.8 or higher**
- **`playerctl`** for media player integration

### Media Players

- **Spotify Desktop** (required)

### Supported Hardware

- **Logitech G213 Prodigy** (single region supported)
- Additional RGB devices (planned support)

## 🚀 Installation

### Quick Install

```bash
# Clone with submodules
git clone --recurse-submodules https://github.com/abdellatif-temsamani/BeatBoard
cd BeatBoard

# Set up virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Verify Installation

```bash
# Test basic functionality
python main.py --help
```

## 🎮 Usage

### Single Color Change

Extract colors from the current song and apply once:

```bash
python main.py
```

### Continuous Mode

Follow the playing song and update colors in real-time:

```bash
python main.py --follow
```

Press `Ctrl+C` to stop following.

### Advanced Options

```bash
# Specify hardware
python main.py --hardware g213

# Debug mode
python main.py --debug
```

## 🖥️ Supported Hardware

### Currently Supported

- **Logitech G213 Prodigy** - single region supported

### Planned Support

- Razer keyboards
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

- **"playerctl not found"**: Install with `sudo apt install playerctl`
  (Ubuntu/Debian)
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
