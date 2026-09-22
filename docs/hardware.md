# Hardware Documentation

## Hardware Support Overview

BeatBoard interfaces with RGB hardware through a modular hardware abstraction
layer that allows for easy extension to new devices. The system uses a
command-based approach where each hardware type defines executable commands that
accept hex color values.

## Platform Support

### Linux
On Linux, BeatBoard uses direct USB access and system tools for hardware control:
- Direct USB communication via libusb (G213)
- System tools like `razer-cli` and `asusctl`
- USB device detection via PyUSB
- Linux DMI for system vendor detection
- Default Spotify integration via `playerctl`
- Optional Spotify API integration via `--api` flag

### macOS/Windows
On macOS and Windows, hardware support depends on the availability of platform-specific
control tools:
- Platform-compatible versions of `razer-cli` (if available)
- Platform-compatible versions of `asusctl` (if available)
- Alternative RGB control software integration
- Manual hardware specification may be required
- Spotify integration via `--api` flag (required since `playerctl` is unavailable)

**Note:** macOS/Windows support for RGB hardware is evolving. Not all Linux tools have
macOS/Windows equivalents. You may need to use manufacturer-provided software or
specify hardware manually with the `--hardware` flag.

### Architecture Overview

The hardware abstraction layer consists of three main components:

1. **Hardware Registry** (`src/beatboard/hardware.py`): Central registry mapping
   hardware names to command templates
2. **Command Generation**: Dynamic command building based on selected hardware
   and color values
3. **Execution Layer**: Asynchronous subprocess execution of hardware control
   commands

When `--hardware` is omitted, BeatBoard automatically detects controllable
hardware. An explicit `--hardware` selection always takes precedence.

**Linux:**
- Logitech G213 keyboards are matched by USB IDs `046d:c336`.
- Razer USB devices are matched by vendor ID `1532` and require `razer-cli`.
- Asus USB devices or Asus systems are detected when `asusctl` is available.

**macOS/Windows:**
- Hardware detection is limited by tool availability and USB access
- Razer devices require platform-compatible `razer-cli`
- Asus devices require platform-compatible `asusctl`
- Manual hardware specification with `--hardware` is recommended

If no supported hardware is detected, BeatBoard exits with guidance to connect a
device or use `--hardware` explicitly.

```python
# Example hardware registry structure
hardware: dict[str, list[str]] = {
    "g213": [sys.executable, _g213_script, "-c"],
    "razer": ["razer-cli", "-c"],
}
```

## Currently Supported Devices

### Logitech G213 Prodigy

**Specifications:**

- **USB Vendor ID**: 0x046d
- **USB Product ID**: 0xc336
- **Regions**: Single region (whole keyboard)
- **Color Format**: RRGGBB hex (e.g., `ff0000` for red)
- **Communication**: Direct USB HID control transfer

**Implementation Details:** The G213 uses a custom Python script
(`G213Colors/G213Colors.py`) that interfaces directly with the device via
libusb. The script handles:

- Kernel driver detachment/reattachment
- USB control transfers with specific request parameters
- Color command formatting (20-byte hex commands)

**Limitations:**

- Single region control only (whole keyboard uniform color)
- Requires root permissions or input group membership for USB access
- No per-key RGB control

**Command Example:**

```bash
python G213Colors.py -c ff0000  # Set keyboard to red
```

### Razer Devices

**Supported Devices:** BeatBoard supports any Razer device compatible with
`razer-cli`, including:

- Razer BlackWidow keyboards
- Razer DeathAdder mice
- Razer Mamba mice
- Other Razer peripherals with RGB support

**Requirements:**

- `razer-cli` must be installed and configured
- Razer drivers (usually `razercfg` or OpenRazer) must be installed
- Device must be recognized by the system

**Implementation Details:** Razer devices use the `razer-cli` command-line tool
which provides a standardized interface for RGB control. BeatBoard simply passes
hex color values to this tool.

**Command Example:**

```bash
razer-cli -c ff0000  # Set all Razer devices to red
```

## Hardware Integration Guide

### How to Add Support for New Devices

Adding support for new RGB hardware involves implementing the command interface
and registering it in the hardware abstraction layer.

#### Required Components

1. **Command Interface**: Executable that accepts hex color values
2. **Color Format**: Consistent RRGGBB hex format (6 characters, no prefix)
3. **Error Handling**: Graceful failure when hardware is unavailable

#### Code Structure and Patterns

**Step 1: Create Hardware Control Script**

Create a standalone script or command that accepts color values:

```python
#!/usr/bin/env python3
import sys
import your_hardware_library

def set_color(color_hex):
    # Validate color format
    if len(color_hex) != 6:
        print("Invalid color format")
        sys.exit(1)

    # Convert hex to RGB
    r = int(color_hex[0:2], 16)
    g = int(color_hex[2:4], 16)
    b = int(color_hex[4:6], 16)

    # Control hardware
    your_hardware_library.set_rgb(r, g, b)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: script.py <color_hex>")
        sys.exit(1)

    set_color(sys.argv[1])
```

**Step 2: Register in Hardware Module (or add a YAML plugin)**

Preferred for most users: drop a YAML file in `~/.config/beatboard/plugins/` – see `docs/plugins.md`. For built-ins, add your hardware to `src/beatboard/hardware.py`:

```python
# Add import for your script path
_your_script = os.path.join(os.path.dirname(__file__), "your_device", "control.py")

hardware: dict[str, list[str]] = {
    "g213": [sys.executable, _g213_script, "-c"],
    "razer": ["razer-cli", "-c"],
    "your_device": [sys.executable, _your_script],  # No -c flag needed
}
```

#### Testing Procedures

**Unit Testing:**

```python
def test_your_device_command():
    commands = get_command(["your_device"], "ff0000")
    assert len(commands) == 1
    assert commands[0][0] == sys.executable
    assert commands[0][-1] == "ff0000"
```

**Integration Testing:**

1. Verify hardware detection
2. Test color setting with known values
3. Test error handling when device unavailable
4. Test with BeatBoard's color extraction pipeline

**Manual Testing Checklist:**

- [ ] Hardware detected by system
- [ ] Permissions configured correctly
- [ ] Color changes work with direct command
- [ ] Integration with BeatBoard color extraction
- [ ] Error handling when hardware disconnected
- [ ] Performance impact assessment

## Technical Specifications

### Color Formats Supported

- **Primary Format**: RRGGBB hex (6 characters, uppercase)
- **Examples**: `FF0000` (red), `00FF00` (green), `0000FF` (blue)
- **Validation**: 6 hexadecimal characters only

### Command Protocols Used

**Logitech G213:**

- USB HID control transfers
- Request Type: 0x21
- Request: 0x09
- Value: 0x0211
- Index: 0x0001
- Data: 20-byte hex commands

**Razer Devices:**

- Command-line interface via `razer-cli`
- Simple argument passing: `razer-cli -c <color>`

### Hardware Communication Methods

- **Direct USB**: G213 uses libusb for raw device communication
- **System Tools**: Razer uses `razer-cli` wrapper around system drivers
- **Asynchronous Execution**: All hardware commands run in asyncio subprocess
  calls

## Troubleshooting

### Common Hardware Issues

**Permission Denied Errors:**

```
Error: Permission denied accessing USB device
```

**Solutions:**

- Add user to `input` group: `sudo usermod -a -G input $USER`
- Or run with elevated permissions (not recommended)
- Restart session after group changes

**Device Not Found:**

```
USB device not found!
```

**Solutions:**

- Verify device is connected and powered
- Check USB permissions
- Test with direct hardware control script
- Verify device IDs match expected values

**Color Not Changing:**

- Check if device firmware is up to date
- Verify device supports RGB control
- Test with manufacturer's software
- Check for conflicting RGB control software

### Permission Problems

**Linux USB Access:** BeatBoard requires access to USB devices for direct
hardware control. The recommended approach is group membership rather than
running as root.

```bash
# Add to input group (recommended)
sudo usermod -a -G input $USER
# Logout and login again

# Alternative: Run with sudo (not recommended for regular use)
sudo beatboard
```

**Windows Hardware Access:** Windows hardware access typically uses manufacturer
drivers and control software:
- Ensure manufacturer drivers are installed
- Run BeatBoard with appropriate permissions if needed
- Some RGB control software may require administrator privileges
- Check Windows Device Manager for hardware recognition

**Razer Driver Setup:** For Razer devices, ensure the appropriate drivers are
installed:

```bash
# Ubuntu/Debian
sudo apt install razer-daemon razer-cli

# Arch Linux
sudo pacman -S razer-cli

# Enable and start service
sudo systemctl enable razer-daemon
sudo systemctl start razer-daemon
```

### Device Detection Failures

**Debug Steps:**

1. List connected USB devices:

   ```bash
   lsusb | grep -i logitech  # For G213
   lsusb | grep -i razer     # For Razer devices
   ```

2. Test direct hardware access:

   ```bash
   python G213Colors.py -c ff0000  # Test G213
   razer-cli -c ff0000             # Test Razer
   ```

3. Check system logs:
   ```bash
   dmesg | grep -i usb
   journalctl -f | grep -i razer
   ```

**Common Detection Issues:**

- Device connected after BeatBoard startup
- Conflicting kernel drivers
- Insufficient USB permissions
- Device in power-saving mode

### Debug Procedures

**Enable Debug Mode:**

```bash
# Linux
beatboard --debug --hardware g213

# Windows
beatboard --api --debug --hardware g213
```

**Verbose Hardware Logging:** The debug flag shows:

- Command generation process
- Executed hardware commands
- Subprocess return codes
- Error messages from hardware scripts

**Manual Hardware Testing:**

```bash
# Linux: Test G213 directly
cd src/beatboard/G213Colors
python G213Colors.py -c ff0000

# Linux: Test Razer devices
razer-cli --help
razer-cli -l  # List devices
razer-cli -c ff0000

# Mac/Windows: Test with manufacturer software
# Use manufacturer-provided RGB control tools
# Verify device recognition in Device Manager/System Information
```

## Mac/Windows Hardware Integration

### Platform-Specific Considerations

Mac and Windows hardware support differs from Linux in several key ways:

**Driver Model:**
- Mac/Windows use manufacturer-provided drivers
- Direct USB access may require special permissions
- Hardware abstraction is different from Linux

**Tool Availability:**
- Not all Linux RGB tools have Mac/Windows equivalents
- Manufacturer software may be required
- Command-line integration may be limited

**Detection Limitations:**
- USB device detection may be restricted
- System vendor detection is not available
- Manual hardware specification is often required

### Recommended Mac/Windows Setup

**For Razer Devices:**
1. Install Razer Synapse (manufacturer software)
2. Check for platform-compatible `razer-cli` alternatives
3. Use `--hardware razer` with manual specification if needed

**For Asus Devices:**
1. Install Armoury Crate (manufacturer software)
2. Check for platform-compatible `asusctl` alternatives
3. Use `--hardware asus` with manual specification if needed

**For Logitech G213:**
1. Install Logitech G Hub (manufacturer software)
2. The G213 script may not work directly on Mac/Windows
3. Consider alternative RGB control methods

### Platform-Specific Hardware Integration Pattern

When adding Mac/Windows support for a device, consider:

1. **Identify platform-compatible control tools:**
   - Check if manufacturer provides CLI tools
   - Look for open-source platform alternatives
   - Consider API integrations if available

2. **Test detection limitations:**
   - USB detection may not work on Mac/Windows
   - Plan for manual hardware specification
   - Provide clear setup instructions

3. **Document platform differences:**
   - Clearly note platform-specific requirements
   - Provide alternative setup methods
   - Include troubleshooting for platform-specific issues

## Contributing Hardware Support

### Steps for Contributors

1. **Research Phase:**
   - Document device specifications (USB IDs, protocols)
   - Identify existing control libraries or tools
   - Assess hardware compatibility requirements

2. **Implementation Phase:**
   - Create hardware control module
   - Implement command interface
   - Add to hardware registry
   - Update type hints and documentation

3. **Testing Phase:**
   - Unit tests for command generation
   - Integration tests with color pipeline
   - Manual testing on real hardware
   - Cross-platform compatibility checks (Linux/Mac/Windows)

4. **Documentation Phase:**
   - Update hardware documentation
   - Add device specifications
   - Include setup instructions
   - Document known limitations

### Testing Requirements

**Required Tests:**

- Command generation validation
- Color format handling
- Error handling for unavailable hardware
- Integration with BeatBoard's color extraction

**Hardware Testing:**

- Test on actual device when possible
- Document test environment (OS, driver versions)
- Provide fallback testing methods for CI/CD

### Documentation Standards

**Device Documentation Template:**

```markdown
### Device Name

**Specifications:**

- USB Vendor/Product IDs
- Supported regions/features
- Color format requirements

**Requirements:**

- Driver/software dependencies
- System permissions needed
- Platform-specific requirements (Linux/Mac/Windows)

**Implementation Notes:**

- Control method used
- Known limitations
- Performance characteristics
- Platform support status (Linux/Mac/Windows/All)
```

**Code Documentation:**

- Comprehensive docstrings for hardware modules
- Inline comments for complex USB protocols
- Error handling documentation
- Performance considerations

---

_For questions about hardware support, please open an issue on the
[BeatBoard GitHub repository](https://github.com/abdellatif-temsamani/BeatBoard/issues)._
</content>
<parameter name="filePath">docs/hardware.md
