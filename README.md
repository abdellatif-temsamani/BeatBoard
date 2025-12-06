Perfect! Based on your folder structure, here’s an updated and precise
**README** for your BeatBoard project:

---

# BeatBoard 🎵💡

BeatBoard is a CLI tool for Linux that **changes your keyboard color** based on
the **currently playing song**. It extracts colors from the album art and
selects vibrant, dominant colors for a dynamic music-light experience.

---

## Features

- Fetch album art of the currently playing song via `playerctl`.
- Extract vibrant, non-neutral colors from album art.
- Apply the most prominent color to your keyboard using `G213Colors`.
- Optionally follow the song in real-time with `python main.py --follow`.
- similar to how Spotify does it (not 100% accurate)

---

## Requirements

- Linux system
- Python 3.13+
- `pip` and virtual environment support
- `playerctl` installed
- `spotify app` installed
- Python dependencies: see `requirements.txt`
- Compatible RGB hardware

---

## Installation

Clone the repository and set up a Python virtual environment:

```bash
git clone --recurse-submodules https://github.com/abdellatif-temsamani/BeatBoard
cd BeatBoard
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Usage

### One-time color change:

```bash
python main.py
```

### Follow each song automatically:

```bash
python main.py --follow
```

---

## Supported hardware

- Logitech G213 Prodigy keyboard

> NOTE: i will be adding args support to make it easier to use with other
> hardware in the future. PRs are welcome!

---

## Contributing

Contributions and suggestions are welcome! Open issues or pull requests for
improvements.

---

## License

MIT License

---

<!-- TODO: add a GIF example -->
