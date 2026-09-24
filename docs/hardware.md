# Hardware Documentation

## Hardware Support Overview

BeatBoard interfaces with RGB hardware through a modular hardware abstraction
layer that is **YAML-driven** and **plugin-extensible**. Built-in devices are
declared as YAML manifests in `src/beatboard/core_plugins/*.yaml` and loaded
at import time; community drivers are drop-in YAML files in
`~/.config/beatboard/plugins/` (see `docs/plugins.md`). All drivers use a
uniform command-based approach: a template `list[str]` with an optional
`{color}` / `{hex}` placeholder that is expanded to a 6-char `RRGGBB` hex
value and executed as an asyncio subprocess.

## Platform Support

### Linux
On Linux, BeatBoard uses direct USB access and system tools for hardware control:
- Direct USB communication via PyUSB/libusb (G213)
- System tools like `razer-cli` and `asusctl`
- USB device detection via PyUSB (`usb.core.find`)
- Linux DMI for system vendor detection (`/sys/class/dmi/id/sys_vendor`)
- Default Spotify integration via `playerctl`
- Optional Spotify API integration via `--api` flag

### macOS/Windows
On macOS and Windows, hardware support depends on the availability of platform-specific
control tools:
- Platform-compatible versions of `razer-cli` (if available)
- Platform-compatible versions of `asusctl` (if available)
- Alternative RGB control software integration (e.g. OpenRGB)
- Manual hardware specification may be required
- Spotify integration via `--api` flag (required since `playerctl` is unavailable)

**Note:** macOS/Windows support for RGB hardware is evolving. Not all Linux tools have
macOS/Windows equivalents. You may need to use manufacturer-provided software or
specify hardware manually with the `--hardware` flag.

### Architecture Overview

The hardware abstraction layer is **`src/beatboard/hardware/`** – a package with a
facade that preserves the flat `beatboard.hardware` / `beatboard.hardware` import
path. Built-ins are no longer hard-coded; they are YAML manifests in
`src/beatboard/core_plugins/` loaded by `core.py` into the registry.

```
src/beatboard/hardware/
├── __init__.py      # facade – re-exports flat API (registry + core + platform + detect + commands)
├── constants.py     # leaf – _SYSTEM_VENDOR_PATHS (no deps)
├── registry.py      # single source of mutable state: hardware dict, _core_detect, _plugin_*,
│                    # register_plugin_hardware(), clear_plugin_hardware(), get_all_hardware()
├── core.py          # YAML loader – _g213_script, _resolve_core_command(), _find_core_plugins_dirs(),
│                    # _load_core_hardware() → populates hardware + _core_detect at import
├── platform.py      # OS/USB – system(), is_windows(), is_linux(), _connected_usb_devices(),
│                    # _system_vendor(), USBDevice protocol
├── detect.py        # detection – _plugin_matches_detect(), detect_hardware()
└── commands.py      # command building – _build_plugin_command(), get_command()
```

Support packages:

- `src/beatboard/core_plugins/*.yaml` – built-in manifests (`g213.yaml`, `razer.yaml`, `asus.yaml`, `g502.yaml`)
- `src/beatboard/plugins/` – community plugin engine (`loader.py`, `models.py:DetectSpec/HardwareSpec/Plugin`,
  `registry.py:extension_registry`, `hooks.py`)

Layering (as enforced in `AGENTS.md`):

`constants.py` (no deps) → `registry.py` / `platform.py` (leaves) → `core.py` / `detect.py` / `commands.py`
(uses leaves) → `__init__.py` facade / `plugins/loader.py` (orchestrates). `watcher`/`playerctl/apply.py`
imports leaves, never the reverse. `src/beatboard/G213Colors/G213Colors.py` is the vendor driver
submodule invoked by the `g213` template.

When `--hardware` is omitted, BeatBoard auto-detects controllable hardware via
`detect_hardware()` and caches the result in SQLite (`cache/db.py: get_cached_hardware`).
An explicit `--hardware` selection always takes precedence. `--refresh-hardware`
forces re-detection. Use `--debug plugins` or `--debug all` to log
`plugins loaded: N from <dir>` and `detect: usb_ids=...`.

**Linux detection:**
- `g213` – USB `046d:c336` alone (no executable required)
- `razer` – vendor `1532` (any product) **AND** `razer-cli` on `$PATH`
- `asus` – (vendor `0B05` **OR** DMI `system_vendor` contains `asus`) **AND** `asusctl` on `$PATH`
- `g502` – USB `046d:c08b` **AND** `ratbagctl` on `$PATH`
- Community plugins – evaluated by the same engine (see `docs/plugins.md` detection semantics)

**macOS/Windows:**
Detection is executable-only. USB vendor checks and `system_vendor` are ignored:
- `g213` never auto-detects (USB-only, no executable)
- `razer` requires `razer-cli`, `asus` requires `asusctl`, `g502` requires `ratbagctl`,
  `openrgb` requires `openrgb`, etc.
- Manual `--hardware <name>` is the recommended path when the executable is installed.

If no supported hardware is detected, BeatBoard continues without hardware (color
extraction still runs) or exits with guidance to connect a device / use
`--hardware` / check `beatboard --doctor`.

```python
# Example – built-in registry is populated from YAML at import time
# src/beatboard/core_plugins/g213.yaml → hardware["g213"] = [sys.executable, _g213_script, "-c", "{color}"]
# src/beatboard/core_plugins/razer.yaml → hardware["razer"] = ["razer-cli", "-c"]
# Community plugin ~/.config/beatboard/plugins/openrgb.yaml → _plugin_hardware["openrgb"]
from beatboard.hardware import get_all_hardware, get_command, detect_hardware

all_hw = (
    get_all_hardware()
)  # {"g213": [...], "razer": [...], "asus": [...], "g502": [...]} + plugins
detected = detect_hardware()  # uses PyUSB + shutil.which + DMI
commands = get_command(['g213', 'razer'], 'ff0000')
# → [[sys.executable, "…/G213Colors/G213Colors.py", "-c", "ff0000"], ["razer-cli", "-c", "ff0000"]]
```

## Currently Supported Devices

### Logitech G213 Prodigy

**Specifications:**

- **USB Vendor ID**: `0x046d`
- **USB Product ID**: `0xc336`
- **Regions**: Single region (whole keyboard)
- **Color Format**: RRGGBB hex (e.g., `ff0000` for red)
- **Communication**: Direct USB HID control transfer
- **Built-in manifest**: `src/beatboard/core_plugins/g213.yaml` (`hardware.command: ["__python__", "__g213_script__", "-c", "{color}"]`, `detect.usb: [{vendor: 0x046D, product: 0xC336}]`)

**Implementation Details:** The G213 uses the bundled vendor script
`src/beatboard/G213Colors/G213Colors.py` which interfaces directly with the
device via PyUSB/libusb. The script handles:

- Kernel driver detachment/reattachment on interface `1`
- USB control transfers (`bmRequestType 0x21`, `bRequest 0x09`, `wValue 0x0211`, `wIndex 0x0001`)
- 20-byte hex command formatting (`11ff0c3a{field}01{color}0200000000000000000000`)

**Limitations:**

- Single region control only (whole keyboard uniform color; multi-segment `-c <c1> … <c5>` is supported by the script but BeatBoard sends one color via field `0`)
- Requires permissions for USB access (`input` group on Linux) – see `beatboard --doctor`
- No per-key RGB control
- **Windows/macOS:** never auto-detected (USB-only, no executable); use manufacturer software or `--hardware g213` with a platform-compatible replacement

**Command Example:**

```bash
python src/beatboard/G213Colors/G213Colors.py -c ff0000  # Set keyboard to red (via BeatBoard template)
beatboard --hardware g213 --debug command                 # show expanded command
```

### Razer Devices

**Supported Devices:** Any Razer device compatible with `razer-cli` (OpenRazer),
including BlackWidow keyboards, DeathAdder/Mamba mice, and other RGB peripherals.

**Requirements:**

- `razer-cli` must be installed and on `$PATH`
- OpenRazer daemon/drivers (`razer-daemon`) must be installed and running
- Device vendor `1532` visible via `lsusb` (Linux auto-detect requires both USB and executable)

**Built-in manifest:** `src/beatboard/core_plugins/razer.yaml`

```yaml
command: ["razer-cli", "-c"]          # color appended → razer-cli -c ff0000
detect:
  usb: [{vendor: 0x1532}]            # any product with vendor 1532
  executables: ["razer-cli"]
```

**Implementation:** Thin wrapper around `razer-cli`. BeatBoard expands `get_command(["razer"], "ff0000")`
to `["razer-cli", "-c", "ff0000"]`; `{color}` placeholder in a community fork would be replaced in-place
instead of appended (see `hardware/commands.py: _build_plugin_command`).

**Command Example:**

```bash
razer-cli -c ff0000              # Set all Razer devices to red
beatboard --hardware razer --debug command
```

### Asus Devices

**Supported Devices:** Asus motherboards, laptops, and peripherals exposing Aura
via `asusctl` (e.g. ROG/TUF series). Detection also matches DMI system vendor
`asus` so an Asus laptop without a distinct Aura USB ID can still be detected.

**Requirements:**

- `asusctl` must be installed and on `$PATH`
- Either Asus USB vendor `0b05` present **or** DMI `/sys/class/dmi/id/sys_vendor` contains `asus` (case-insensitive)
- **Linux auto-detect** = (usb_match **OR** vendor_match) **AND** executable; **Windows** = executable only

**Built-in manifest:** `src/beatboard/core_plugins/asus.yaml`

```yaml
command: ["asusctl", "aura", "static", "-c"]   # → asusctl aura static -c ff0000
detect:
  usb: [{vendor: 0x0B05}]
  executables: ["asusctl"]
  system_vendor: "asus"
```

**Command Example:**

```bash
asusctl aura static -c ff0000
beatboard --hardware asus --debug command
```

### Logitech G502 SE HERO

**Specifications:**

- **USB Vendor ID**: `0x046d`
- **USB Product ID**: `0xc08b`
- **Color Format**: RRGGBB hex
- **Tool**: `ratbagctl` (libratbag / Piper)

**Built-in manifest:** `src/beatboard/core_plugins/g502.yaml`

```yaml
command: ["sh", "-c", "D=$(/usr/bin/python3 /usr/sbin/ratbagctl list | grep -i g502 | cut -d: -f1 | tr -d ' '); [ -n \"$D\" ] && /usr/bin/python3 /usr/sbin/ratbagctl \"$D\" led 0 set color {color} && /usr/bin/python3 /usr/sbin/ratbagctl \"$D\" led 1 set color {color}"]
detect:
  usb: [{vendor: 0x046D, product: 0xC08B}]
  executables: ["ratbagctl"]
```

The template discovers the ratbag device id at runtime and sets both LEDs; `{color}` is substituted
inside the shell script by `_build_plugin_command`. Auto-detect requires the G502 USB ID and `ratbagctl`.

### OpenRGB (Community Plugin Example)

Not a built-in core plugin – shipped as an example in `examples/plugins/openrgb.yaml`
and loaded from `~/.config/beatboard/plugins/` when present. Demonstrates the
executable-only detection pattern for vendor-agnostic control.

```yaml
name: openrgb
type: hardware
hardware:
  command: ["openrgb", "--color", "{color}"]   # {color} replaced → openrgb --color ff0000
  detect:
    executables: ["openrgb"]                  # auto-detects whenever openrgb is on $PATH
```

See `docs/plugins.md` for the full schema (`usb`, `executables`, `system_vendor`).
Other examples: `examples/plugins/corsair-k70.yaml` (`ck-corsair-cli`),
`examples/plugins/hue-bridge.yaml`.

## Hardware Integration Guide

### How to Add Support for New Devices

**Preferred path – YAML plugin (no code, no fork):** drop a YAML manifest in
`~/.config/beatboard/plugins/` – see `docs/plugins.md` for the complete schema
and validation rules. This is sufficient for most devices. Restart BeatBoard (or
re-run `load_plugins`/`register_plugins`); the name becomes valid for
`--hardware` and auto-detection.

**Built-in path – contribute a `core_plugins` manifest:** add a YAML file to
`src/beatboard/core_plugins/` and open a PR (requires `allow_reserved=True`
handling in `plugins/models.py: validate_plugin_dict` for core names). The
`hardware/registry.py: hardware` dict and `_core_detect` are populated by
`hardware/core.py: _load_core_hardware()` at import.

#### Required Components

1. **Command Interface**: Executable that accepts a 6-char hex color (RRGGBB, no `#`)
2. **Color Format**: Consistent RRGGBB; BeatBoard always passes lower-case e.g. `ff0000`
3. **Error Handling**: Graceful failure when hardware unavailable (BeatBoard runs commands via `asyncio.create_subprocess_exec`)

#### Code Structure and Patterns

**Step 1: Create a YAML plugin (preferred)**

```yaml
# ~/.config/beatboard/plugins/my-device.yaml
name: my-device
version: "1.0.0"
description: "My RGB device via my-tool"
author: "You <you@example.com>"
type: hardware
hardware:
  command: ["my-tool", "-c", "{color}"]   # {color} or {hex} replaced; without placeholder, color is appended
  detect:                                  # optional – omit for manual --hardware only
    usb:
      - vendor: 0x1234
        product: 0x5678            # product optional → any product with vendor
    executables: ["my-tool"]       # all must be on $PATH (shutil.which)
    system_vendor: "MyVendor"      # optional, case-insensitive substring of DMI vendor
```

Or a standalone script invoked by the command:

```python
#!/usr/bin/env python3
import sys
import your_hardware_library


def set_color(color_hex: str) -> None:
    if len(color_hex) != 6:
        print('Invalid color format', file=sys.stderr)
        sys.exit(1)
    r, g, b = int(color_hex[0:2], 16), int(color_hex[2:4], 16), int(color_hex[4:6], 16)
    your_hardware_library.set_rgb(r, g, b)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f'Usage: {sys.argv[0]} <color_hex>', file=sys.stderr)
        sys.exit(1)
    set_color(sys.argv[1])
```

```yaml
hardware:
  command: ["/usr/bin/python3", "/path/to/my-device.py", "{color}"]
  detect:
    executables: ["my-tool"]
```

**Step 2: Register / use it**

```bash
mkdir -p ~/.config/beatboard/plugins
cp my-device.yaml ~/.config/beatboard/plugins/
beatboard --hardware my-device --debug plugins   # validate load
beatboard --hardware my-device --once            # manual test
beatboard --debug all                            # auto-detect test (shows usb_ids / vendor / executables)
```

For a built-in, add the YAML to `src/beatboard/core_plugins/` instead and ensure
`core.py: _resolve_core_command` can expand placeholders (`__python__`, `__g213_script__`)
if you need the interpreter or script path.

#### Testing Procedures

**Unit Testing (uses the public facade – `src/beatboard/hardware/__init__.py` re-exports):**

```python
from beatboard.hardware import (
    get_command,
    detect_hardware,
    clear_plugin_hardware,
    register_plugin_hardware,
)
from beatboard.plugins.models import DetectSpec, UsbId
from types import SimpleNamespace


def test_your_device_command():
    commands = get_command(['my-device'], 'ff0000')
    assert len(commands) == 1
    assert 'ff0000' in commands[0]


def test_your_device_detect():
    spec = DetectSpec(
        usb=[UsbId(vendor=0x1234, product=0x5678)], executables=['my-tool']
    )
    register_plugin_hardware('my-device', ['my-tool', '-c', '{color}'], spec)
    devices = [SimpleNamespace(idVendor=0x1234, idProduct=0x5678)]
    assert 'my-device' in detect_hardware(
        devices=devices,
        executable_finder=lambda n: '/usr/bin/my-tool' if n == 'my-tool' else None,
        system_vendor='Generic',
    )
    clear_plugin_hardware()
```

**Integration Testing:**

1. Verify `get_all_hardware()` includes your name and `beatboard --help` lists it
2. Test color setting with known values: `beatboard --hardware my-device --once --debug command`
3. Test error handling when device unavailable / executable missing
4. Test with BeatBoard's color extraction pipeline (play a track, observe `playerctl/apply.py: _run_hardware`)

**Manual Testing Checklist:**

- [ ] Hardware detected by `detect_hardware()` (`--debug all` shows `detect: usb_ids=…`)
- [ ] Permissions configured correctly (`beatboard --doctor` → Permissions / OpenRGB checks)
- [ ] Color changes work with direct command (`my-tool -c ff0000`)
- [ ] Integration with BeatBoard color extraction (Vibrant palette → hardware)
- [ ] Error handling when hardware disconnected (subprocess non-zero, no crash)
- [ ] Performance impact assessment (subprocess latency, cache hits)

## Technical Specifications

### Color Formats Supported

- **Primary Format**: RRGGBB hex (6 characters, lowercase as passed, uppercase accepted by G213 script)
- **Examples**: `ff0000` (red), `00ff00` (green), `0000ff` (blue) – BeatBoard always emits lower-case
- **Validation**: 6 hexadecimal characters; `hardware/commands.py: get_command` appends/replaces without strict validation, `G213Colors.py: checkColorHex` validates strictly

### Command Protocols Used

Command expansion is in `hardware/commands.py: _build_plugin_command`:

- If any part of the template contains `{color}` or `{hex}`, every occurrence is replaced with the 6-char hex
  - `["openrgb", "--color", "{color}"]` → `["openrgb", "--color", "ff0000"]`
  - `["hue-cli", "set", "--color={color}"]` → `["hue-cli", "set", "--color=ff0000"]`
  - g213: `["__python__", "__g213_script__", "-c", "{color}"]` resolved via `hardware/core.py: _resolve_core_command`
- Otherwise, color is appended as last argument: `["razer-cli", "-c"]` → `["razer-cli", "-c", "ff0000"]`
- Core placeholders `_resolve_core_command`: `__python__` → `sys.executable`, `__g213_script__` → `src/beatboard/G213Colors/G213Colors.py`

**Logitech G213:**

- USB HID control transfers via `G213Colors.py: sendData`
- `bmRequestType 0x21`, `bRequest 0x09`, `wValue 0x0211`, `wIndex 0x0001`, endpoint `0x82`
- Data: 20-byte hex command `11ff0c3a{field}01{color}0200000000000000000000` (`_build_plugin_command` supplies `{color}`)

**Razer Devices:**

- `razer-cli -c <color>` via `razer-cli` (OpenRazer)

**Asus Devices:**

- `asusctl aura static -c <color>`

**G502:**

- `sh -c '… ratbagctl <dev> led 0/1 set color {color}'` – shell discovers device id via `ratbagctl list`

### Hardware Communication Methods

- **Direct USB**: G213 uses PyUSB/libusb raw control transfers
- **System Tools**: Razer (`razer-cli`), Asus (`asusctl`), G502 (`ratbagctl`), OpenRGB (`openrgb`) via `shutil.which`
- **Asynchronous Execution**: All hardware commands run via `asyncio.create_subprocess_exec` in `src/beatboard/playerctl/apply.py: _run_hardware` (one subprocess per selected hardware, `Globs().debug["command"]` logs return codes)

### Detection Semantics (`hardware/detect.py: _plugin_matches_detect`)

```text
# Linux
if executables: all must be found via shutil.which
if has_usb and has_vendor: require (usb_match OR vendor_match) AND executables
elif has_usb: require usb_match AND executables (if declared)
elif has_vendor: require vendor_match AND executables (if declared)
else: require executables (if any) – otherwise manual-only (detect block omitted)

# Windows (hardware/platform.py: is_windows() == True)
# USB/vendor ignored; only executables matter. USB-only drivers (g213) never auto-detect.
if executables: all must be found → detected else not detected
return False
```

`detect_hardware(devices=None, executable_finder=None, system_vendor=None)` – all args injectable for tests.
Enumerates USB via `hardware/platform.py: _connected_usb_devices()` (`usb.core.find(find_all=True)`) and
vendor via `_system_vendor()` (`/sys/class/dmi/id/sys_vendor`).

## Troubleshooting

### Common Hardware Issues

**Permission Denied Errors:**

```
Error: Permission denied accessing USB device
USB device not found!
```

**Solutions (Linux):**

- Add user to `input` group: `sudo usermod -a -G input $USER` → re-login
- Or run once with elevated permissions to verify (not recommended for daily use)
- Run `beatboard --doctor` – the Permissions diagnostic checks `input` group, USB access, and driver daemons
- Restart session after group changes

**Device Not Found:**

```
USB device not found!
```

**Solutions:**

- Verify device is connected and powered (`lsusb | grep -i logitech` / `razer` / `0b05`)
- Check USB permissions / kernel driver (G213 detaches `usbhid` on interface 1)
- Test with direct hardware control script (`python src/beatboard/G213Colors/G213Colors.py -c ff0000` or `razer-cli -c ff0000`)
- Verify device IDs match the YAML `detect.usb` (check `tests/test_hardware.py` for expected IDs)
- Check `beatboard --debug all` output: `detect: usb_ids=[…] vendor='…'`

**Color Not Changing:**

- Check if device firmware is up to date
- Verify device supports RGB control (`razer-cli -l`, `asusctl aura --help`, `ratbagctl list`)
- Test with manufacturer's software to rule out driver issues
- Check for conflicting RGB control software (OpenRGB vs vendor daemon)
- Check subprocess logs: `beatboard --debug command` prints expanded commands and return codes from `playerctl/apply.py`

### Permission Problems

**Linux USB Access:** BeatBoard requires USB access for direct hardware control (G213).
Group membership is preferred over `sudo`.

```bash
# Add to input group (recommended)
sudo usermod -a -G input $USER
# Logout and login again
# Verify
groups | grep input
beatboard --doctor   # checks Permissions + OpenRGB + hardware detection
```

**Windows Hardware Access:** Uses manufacturer drivers / CLI tools:
- Ensure manufacturer drivers are installed
- Run BeatBoard with appropriate permissions if needed
- Some RGB tools may require administrator privileges
- Check Device Manager for hardware recognition; on Windows BeatBoard only auto-detects via executables

**Razer Driver Setup:**

```bash
# Ubuntu/Debian
sudo apt install razer-daemon razer-cli
# Arch Linux
sudo pacman -S razer-cli
sudo pacman -S openrazer-daemon   # if needed
# Enable and start service
sudo systemctl enable razer-daemon
sudo systemctl start razer-daemon
razer-cli -l  # list devices
```

**Asus / G502 / OpenRGB:**

```bash
# Asus
sudo apt install asusctl   # or via asus-linux.org
asusctl aura static -c ff0000

# G502 (libratbag)
sudo apt install ratbagd libratbag-tools
ratbagctl list

# OpenRGB
sudo apt install openrgb   # or https://openrgb.org
openrgb --color ff0000
```

### Device Detection Failures

**Debug Steps:**

1. List connected USB devices:

   ```bash
   lsusb | grep -i logitech   # G213 046d:c336, G502 046d:c08b
   lsusb | grep -i razer      # 1532:xxxx
   lsusb | grep 0b05           # Asus
   ```

2. Test direct hardware access:

   ```bash
   python src/beatboard/G213Colors/G213Colors.py -c ff0000
   razer-cli -c ff0000
   asusctl aura static -c ff0000
   ratbagctl list && ratbagctl <dev> led 0 set color ff0000
   openrgb --color ff0000
   ```

3. Check BeatBoard detection and plugin loading:

   ```bash
   beatboard --debug all --once       # shows detect: usb_ids / vendor / executables / g213_ids
   beatboard --debug plugins --once   # shows plugins loaded: N from ~/.config/beatboard/plugins
   beatboard --doctor                 # structured diagnostics (hardware + plugins + permissions)
   journalctl -f | grep -i razer     # daemon logs
   dmesg | grep -i usb
   ```

**Common Detection Issues:**

- Device connected after BeatBoard startup – use `--refresh-hardware` or restart BeatBoard
- Conflicting kernel drivers (G213: `usbhid` on interface 1 – BeatBoard detaches it)
- Insufficient USB permissions
- Device in power-saving mode
- Plugin YAML syntax error – file skipped with yellow `Warning: Skipping plugin …` (check `beatboard --debug plugins`)
- Name collision – duplicate `name` or collision with built-in (`g213`/`razer`/`asus`/`g502`) → second file skipped

### Debug Procedures

**Enable Debug Mode:**

```bash
# Linux – all categories (command + palette + cache + api + plugins)
beatboard --debug all --once
beatboard --debug plugins --once      # only plugin loading
beatboard --debug command --once      # only expanded hardware commands
beatboard --debug cache --once        # cache + detection logs

# Windows – API mode
beatboard --api --debug all --once
```

**Verbose Hardware Logging:** Debug flags show:

- `command` – expanded hardware commands and subprocess return codes (`playerctl/apply.py`)
- `plugins` – scanned dir, loaded count, skipped files (`plugins/loader.py`)
- `all` – USB IDs, DMI vendor, executable presence (`hardware/detect.py`)
- `cache` – cached hardware, migrations

**Manual Hardware Testing:**

```bash
# Linux: Test G213 directly
python src/beatboard/G213Colors/G213Colors.py -c ff0000

# Linux: Test Razer/Asus/G502/OpenRGB
razer-cli --help; razer-cli -l; razer-cli -c ff0000
asusctl --help; asusctl aura static -c ff0000
ratbagctl list; ratbagctl <id> led 0 set color ff0000
openrgb --help; openrgb --color ff0000

# Inspect registry directly (useful for plugin development)
python -c "from beatboard.hardware import get_all_hardware, detect_hardware; print(get_all_hardware()); print(detect_hardware())"

# Validate a plugin without running BeatBoard
python -c "from beatboard.plugins import load_plugins, register_plugins; p,e=load_plugins('~/.config/beatboard/plugins'); print(p, e)"

# Full diagnostics
beatboard --doctor
```

## Mac/Windows Hardware Integration

### Platform-Specific Considerations

Mac and Windows hardware support differs from Linux in several key ways:

**Driver Model:**
- Mac/Windows use manufacturer-provided drivers (Synapse, G Hub, Armoury Crate)
- Direct USB access may require special permissions or may be blocked
- Hardware abstraction relies on CLI tools on `$PATH`, not raw USB

**Tool Availability:**
- Not all Linux RGB tools have Mac/Windows equivalents
- Manufacturer software may be required
- Command-line integration may be limited – consider OpenRGB as cross-platform alternative

**Detection Limitations:**
- On Windows, `_connected_usb_devices()` is ignored and `_system_vendor()` returns `""`
  (see `hardware/platform.py: is_windows()` and `hardware/detect.py: detect_hardware` Windows branch)
- `system_vendor` detection (Linux DMI) is not available
- USB-only devices like G213 never auto-detect; manual `--hardware` is required

### Recommended Mac/Windows Setup

**For Razer Devices:**
1. Install Razer Synapse (manufacturer software)
2. Check for platform-compatible `razer-cli` / OpenRazer alternatives; if unavailable, consider OpenRGB
3. Use `--hardware razer --api` with manual specification if executable is on `$PATH`, otherwise use a YAML plugin pointing at the available CLI

**For Asus Devices:**
1. Install Armoury Crate (manufacturer software)
2. Check for platform-compatible `asusctl` alternatives
3. Use `--hardware asus --api` with manual specification if needed; vendor DMI check is Linux-only

**For Logitech G213:**
1. Install Logitech G Hub (manufacturer software)
2. The G213 PyUSB script (`G213Colors.py`) requires libusb and kernel detach – typically Linux-only
3. Consider alternative RGB control via OpenRGB if G213 is exposed through it

**For Generic / Cross-Platform:**
1. Install OpenRGB (`https://openrgb.org`) – works on Linux/Windows
2. Drop `examples/plugins/openrgb.yaml` into `~/.config/beatboard/plugins/` (or your `plugin_dir`)
3. Use `--hardware openrgb --api`

### Platform-Specific Hardware Integration Pattern

When adding Mac/Windows support for a device via YAML plugin, consider:

1. **Identify platform-compatible control tools:**
   - Check if manufacturer provides CLI tools on `$PATH`
   - Look for open-source cross-platform alternatives (OpenRGB)
   - Consider wrapping a GUI tool with a small CLI shim that accepts `{color}`

2. **Test detection limitations:**
   - On Windows, USB detection is ignored – declare `executables` so auto-detect can work via `shutil.which`
   - If no executable is suitable, omit `detect` for manual-only and document `--hardware <name> --api`
   - Provide clear per-platform setup instructions

3. **Document platform differences:**
   - Clearly note `detect` behavior on Windows vs Linux
   - Provide alternative setup methods per OS
   - Include troubleshooting for platform-specific permissions

## Contributing Hardware Support

### Steps for Contributors

1. **Research Phase:**
   - Document device specifications (USB vendor/product IDs via `lsusb`, DMI vendor string, CLI tool)
   - Identify existing control libraries or tools (does `openrgb`, `razer-cli`, `ratbagctl` already cover it?)
   - Assess whether a community YAML plugin is sufficient or a built-in `core_plugins` manifest is warranted

2. **Implementation Phase:**
   - **Community driver:** copy `examples/plugins/corsair-k70.yaml` or `openrgb.yaml`, set `name`/`command`/`detect`, place in `~/.config/beatboard/plugins/`
   - **Built-in:** add `src/beatboard/core_plugins/<name>.yaml` (`name`, `command`, optional `detect` with `usb`/`executables`/`system_vendor`), using `__python__`/`__g213_script__` placeholders if needed via `hardware/core.py: _resolve_core_command`
   - No Python code change required for most devices; if a new driver script is needed, place it near its domain (e.g. `src/beatboard/G213Colors/`) and reference it from the YAML

3. **Testing Phase:**
   - Unit tests: `tests/test_hardware.py: test_get_command_valid`, `test_detect_hardware_*`
   - Plugin tests: `tests/test_plugins.py` (YAML validation, duplicate names, reserved names, placeholder expansion)
   - Manual testing on real hardware
   - Cross-platform checks (`is_windows()` branch) via `tests/test_hardware.py: test_detect_hardware_on_windows`

4. **Documentation Phase:**
   - Update this file (`docs/hardware.md`) and `docs/plugins.md` if adding an example
   - Add device specifications (USB IDs, executables, DMI vendor, command template)
   - Include setup instructions per platform
   - Document known limitations and `beatboard --doctor` diagnostics

### Testing Requirements

**Required Tests:**

- Command generation: `get_command([name], "ff0000")` contains color (with/without placeholder)
- Color format handling: lower-case 6-char hex, `{color}`/`{hex}` substitution in `hardware/commands.py: _build_plugin_command`
- Error handling: `get_command(["unknown"], …)` raises `ValueError`, unavailable hardware fails gracefully (subprocess non-zero, no crash)
- Detection: USB match, executable presence, vendor match, Windows-only executable path
- Integration: BeatBoard's color extraction → cache → `playerctl/apply.py: _run_hardware`

**Hardware Testing:**

- Test on actual device when possible; document test environment (OS, driver/daemon versions, `lsusb` output)
- Provide fallback testing methods for CI/CD: inject `devices`, `executable_finder`, `system_vendor` into `detect_hardware()`

### Documentation Standards

**Device Documentation Template:**

```markdown
### Device Name

**Specifications:**

- USB Vendor/Product IDs (hex, e.g. 0x046D:0xC336)
- Supported regions/features
- Color format requirements (RRGGBB)
- Built-in manifest path (if core) or example plugin path

**Requirements:**

- Driver/software dependencies and install commands per OS
- System permissions needed (input group, daemon)
- Platform-specific requirements and detection behavior (Linux vs Windows)
- Executables required on $PATH

**Implementation Notes:**

- Command template and placeholder usage
- Control method (direct USB / system tool / OpenRGB)
- Detection logic (usb / executables / system_vendor, Windows executable-only)
- Known limitations and performance characteristics
- Platform support status (Linux / Windows / All) – see hardware/detect.py
```

**Code Documentation:**

- Comprehensive docstrings for `hardware/*.py` and `plugins/models.py: DetectSpec/HardwareSpec`
- Inline comments for USB protocols (`G213Colors.py: sendData` control transfer)
- Error handling documentation (YAML validation → yellow warning, duplicate/reserved name → skip)
- Performance considerations (async subprocess, cache, `--refresh-hardware`)

---

_For questions about hardware support, please open an issue on the
[BeatBoard GitHub repository](https://github.com/abdellatif-temsamani/BeatBoard/issues)._
