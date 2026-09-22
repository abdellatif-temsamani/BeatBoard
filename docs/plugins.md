# Plugins – Community Hardware Drivers & Extensions

BeatBoard now supports **community-built hardware drivers and extensions** as YAML manifests. No code changes required – just drop a `.yaml` file.

## Directory

Default plugin directory:

```
~/.config/beatboard/plugins/
```

You can change it in `~/.config/beatboard/config.yaml`:

```yaml
plugin_dir: "~/my-beatboard-plugins"   # expanded, or null to disable
cache_path: "~/.local/state/beatboard/cache.db"
debug: []
```

- `plugin_dir` is expanded (`~` → `$HOME`) and created if missing.
- Set `plugin_dir: null` or `plugin_dir: ""` to disable all plugins.
- Each `*.yaml` / `*.yml` file in the directory is one plugin.

## Quick start

```bash
mkdir -p ~/.config/beatboard/plugins
cp examples/plugins/corsair-k70.yaml ~/.config/beatboard/plugins/
beatboard --hardware corsair-k70   # use community driver manually
# or let auto-detection pick it up if usb + executable match
beatboard
```

## Hardware plugin schema

```yaml
name: corsair-k70                 # required, unique slug [a-z0-9_-], 1-32 chars
version: "1.0.0"                  # optional, string
description: "..."                # optional
author: "Alice <alice@ex>"        # optional
type: hardware                    # required: hardware | extension
hardware:
  command: ["ck-corsair-cli", "-c", "{color}"]  # required, list[str]
  detect:                         # optional – if omitted, manual --hardware only
    usb:                          # list of vendor/product (hex or decimal)
      - vendor: 0x1b1c
        product: 0x1b49            # product optional → any product with vendor
      - vendor: 0x0b05
    executables: ["ck-corsair-cli"]  # all must be found via $PATH (shutil.which)
    system_vendor: "Corsair"      # case-insensitive substring of Linux DMI vendor
```

**Detection semantics (all declared conditions must pass):**

- If `usb` present → at least one entry matches connected USB devices (vendor + optional product).
- If `executables` present → every executable must be on `$PATH`.
- If `system_vendor` present → substring match against `/sys/class/dmi/id/sys_vendor`.
- If `detect` omitted → plugin is **manual-only** (`--hardware <name>` required).
- On Windows, USB detection is limited; plugins that require USB will not auto-detect unless their executable is also found (mirrors built-in `g213`/`razer`/`asus` logic).

**Command template:**

- `{color}` (or `{hex}`) placeholder is replaced with 6-char hex like `ff0000`.
- If no placeholder, color is appended as last argument (same as built-ins):
  - `["openrgb", "--color", "{color}"]` → `openrgb --color ff0000`
  - `["my-tool", "-c"]` → `my-tool -c ff0000`

## Extension plugin schema

Extensions hook into BeatBoard events (future-proof; currently registered and logged).

```yaml
name: notify-track
type: extension
extension:
  hooks:
    - event: track_change     # one of: track_change, color_applied, pre_color, post_color
      command: ["notify-send", "Now playing {title}"]
    - event: color_applied
      command: ["notify-send", "{color}"]
```

Valid `event` values: `track_change`, `color_applied`, `pre_color`, `post_color`.

Extensions are loaded into an in-memory registry (`beatboard.plugins.extension_registry`) for future dispatch.

## Validation & errors

- Invalid YAML or missing required keys → file **skipped** with a yellow warning, BeatBoard continues.
- Duplicate `name` → second file skipped.
- Name collides with built-in (`g213`, `razer`, `asus`) → skipped.
- Detection block without any condition → validation error, skipped.

Start BeatBoard with `--debug cache` to see `plugins loaded: N from <dir>`.

## Discovery & testing

```bash
# List all available hardware (built-ins + plugins)
beatboard --help   # help shows plugin names as "plugin" source

# Validate a plugin without running BeatBoard
python -c "from beatboard.plugins import load_plugins, register_plugins; p,e=load_plugins('~/.config/beatboard/plugins'); print(p)"

# Integration test helper
python -m pytest tests/test_plugins.py -v
```

## Writing a new driver – checklist

1. Identify how to set color from CLI: `my-tool -c ff0000` or `my-tool --color=ff0000`.
2. Find USB vendor/product via `lsusb` if you want auto-detection.
3. Check that the control tool is on `$PATH`.
4. Copy `examples/plugins/corsair-k70.yaml` and edit `name` + `command` + `detect`.
5. Test: `beatboard --hardware your-name --once --debug command`.

## Security notes

- Plugins only declare a **command list** executed via `subprocess` (no shell, no arbitrary Python). Review community YAML before installing.
- Commands are run with your user privileges – same as built-in `razer-cli`/`asusctl` paths.

## Example community drivers

See `examples/plugins/`:

- `corsair-k70.yaml` – Corsair K70 via `ck-corsair-cli` + USB detection
- `openrgb-generic.yaml` – Generic OpenRGB (executable-only)
- `hue-bridge.yaml` – Hue bridge showing `{color}` placeholder in-arg
- `notify-extension.yaml` – Notification extension (track_change hook)

Want to publish yours? Open a PR adding it to `examples/plugins/` or link your repo in an issue.

## Architecture overview

```
config.yaml plugin_dir ──► ~/.config/beatboard/plugins/*.yaml
                              │
                    loader.py: validate + Plugin dataclass
                              │
                    hardware.py: register_plugin_hardware(name, command, detect)
                              │
                    detect_hardware() ──► _plugin_matches_detect(usb, exe, vendor)
                    get_command() ──► _build_plugin_command(template, color)
                              │
                    args.py HardwareAction validates against get_all_hardware()
```

Loading order in `beatboard_main`:

1. `load_config` → `globs.plugin_dir`
2. `clear_plugin_hardware()` + `clear_extension_registry()` (supports reloads)
3. `load_plugins(plugin_dir)` → warns on invalid files
4. `register_plugins()` → populates `hardware._plugin_hardware` / `extension_registry`
5. `parser.parse_args()` → now knows plugin names, so `--hardware foo` works
6. `detect_hardware()` → considers plugins with `detect` block
7. `get_command([...], color)` → expands `{color}` correctly

