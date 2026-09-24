from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PluginValidationError

_NAME_RE = re.compile(r'^[a-z0-9][a-z0-9_-]{1,30}[a-z0-9]$|^[a-z0-9]$')
# valid extension events
VALID_HOOK_EVENTS = {'track_change', 'color_applied', 'pre_color', 'post_color'}

# Type aliases
PluginType = str  # "hardware" | "extension"


@dataclass(slots=True, frozen=True)
class UsbId:
    vendor: int
    product: int | None = None


@dataclass(slots=True, frozen=True)
class DetectSpec:
    usb: list[UsbId] = field(default_factory=list)
    executables: list[str] = field(default_factory=list)
    system_vendor: str | None = None


@dataclass(slots=True, frozen=True)
class HardwareSpec:
    command: list[str]
    detect: DetectSpec | None = None


@dataclass(slots=True, frozen=True)
class HookSpec:
    event: str
    command: list[str]


@dataclass(slots=True, frozen=True)
class ExtensionSpec:
    hooks: list[HookSpec] = field(default_factory=list)


@dataclass(slots=True, frozen=True)
class Plugin:
    name: str
    version: str
    description: str
    author: str
    type: str
    source_path: Path
    hardware: HardwareSpec | None = None
    extension: ExtensionSpec | None = None


def _parse_vendor_product(value: object) -> int:
    """Parse vendor/product which may be int or hex string like '0x1532'."""
    if isinstance(value, int):
        if not 0 <= value <= 0xFFFF:
            raise ValueError('vendor/product out of range 0x0000-0xFFFF')
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        try:
            if s.startswith('0x'):
                v = int(s, 16)
            else:
                # allow decimal string or hex without prefix? try int auto
                v = int(s, 0)
        except ValueError as exc:
            raise ValueError(f"invalid hex/int '{value}'") from exc
        if not 0 <= v <= 0xFFFF:
            raise ValueError('vendor/product out of range')
        return v
    raise ValueError(
        f'vendor/product must be int or hex string, got {type(value).__name__}'
    )


def validate_plugin_dict(
    data: dict, source_path: Path, *, allow_reserved: bool = False
) -> Plugin:
    """Validate a raw YAML dict and return a Plugin.

    Args:
        allow_reserved: If True, allow names that conflict with core hardware (used for core_plugins).
    Raises PluginValidationError on failure.
    """
    fname = str(source_path)
    if not isinstance(data, dict):
        raise PluginValidationError(fname, 'top level must be a mapping')

    name = data.get('name')
    if not isinstance(name, str) or not name.strip():
        raise PluginValidationError(
            fname, 'name is required and must be a non-empty string'
        )
    name = name.strip()
    if not _NAME_RE.match(name):
        raise PluginValidationError(
            fname,
            "name must be 1-32 chars, lower-case alphanumeric with '-'/'_'",
        )
    # Reserved names conflict with built-ins – only for community plugins
    if not allow_reserved and name in {'g213', 'razer', 'asus'}:
        raise PluginValidationError(
            fname, f"name '{name}' conflicts with built-in hardware"
        )

    version = data.get('version', '0.1.0')
    if not isinstance(version, str) or not version.strip():
        raise PluginValidationError(fname, 'version must be a non-empty string')
    version = version.strip()

    description = data.get('description', '')
    if not isinstance(description, str):
        raise PluginValidationError(fname, 'description must be a string')
    author = data.get('author', '')
    if not isinstance(author, str):
        raise PluginValidationError(fname, 'author must be a string')

    ptype = data.get('type')
    if ptype not in ('hardware', 'extension'):
        raise PluginValidationError(fname, "type must be 'hardware' or 'extension'")

    hardware_spec: HardwareSpec | None = None
    extension_spec: ExtensionSpec | None = None

    if ptype == 'hardware':
        raw_hw = data.get('hardware')
        if not isinstance(raw_hw, dict):
            raise PluginValidationError(
                fname, "hardware: mapping is required for type 'hardware'"
            )
        raw_cmd = raw_hw.get('command')
        if (
            not isinstance(raw_cmd, list)
            or not raw_cmd
            or not all(isinstance(c, str) and c.strip() for c in raw_cmd)
        ):
            raise PluginValidationError(
                fname, 'hardware.command must be a non-empty list of strings'
            )
        command = [c.strip() for c in raw_cmd]  # type: ignore[arg-type]

        # Check for color placeholder: optional {color}. No validation beyond strings.
        raw_detect = raw_hw.get('detect')
        detect_spec: DetectSpec | None = None
        if raw_detect is not None:
            if not isinstance(raw_detect, dict):
                raise PluginValidationError(
                    fname, 'hardware.detect must be a mapping if present'
                )
            detect_spec = _parse_detect(raw_detect, fname)

        hardware_spec = HardwareSpec(command=command, detect=detect_spec)

        # extension block should not be present for hardware? allow but ignore?
        if 'extension' in data:
            raise PluginValidationError(
                fname, "extension block not allowed when type is 'hardware'"
            )

    else:  # extension
        raw_ext = data.get('extension')
        if raw_ext is not None and not isinstance(raw_ext, dict):
            raise PluginValidationError(fname, 'extension must be a mapping if present')
        hooks: list[HookSpec] = []
        if isinstance(raw_ext, dict):
            raw_hooks = raw_ext.get('hooks', [])
            if raw_hooks is None:
                raw_hooks = []
            if not isinstance(raw_hooks, list):
                raise PluginValidationError(fname, 'extension.hooks must be a list')
            for idx, h in enumerate(raw_hooks):
                if not isinstance(h, dict):
                    raise PluginValidationError(
                        fname, f'extension.hooks[{idx}] must be a mapping'
                    )
                event = h.get('event')
                if not isinstance(event, str) or not event.strip():
                    raise PluginValidationError(
                        fname, f'extension.hooks[{idx}].event must be non-empty string'
                    )
                event = event.strip()
                if event not in VALID_HOOK_EVENTS:
                    raise PluginValidationError(
                        fname,
                        f'extension.hooks[{idx}].event must be one of {sorted(VALID_HOOK_EVENTS)}',
                    )
                cmd = h.get('command')
                if (
                    not isinstance(cmd, list)
                    or not cmd
                    or not all(isinstance(c, str) and c.strip() for c in cmd)
                ):
                    raise PluginValidationError(
                        fname,
                        f'extension.hooks[{idx}].command must be non-empty list of strings',
                    )
                hooks.append(HookSpec(event=event, command=[c.strip() for c in cmd]))  # type: ignore[arg-type]
        extension_spec = ExtensionSpec(hooks=hooks)
        if 'hardware' in data:
            raise PluginValidationError(
                fname, "hardware block not allowed when type is 'extension'"
            )

    return Plugin(
        name=name,
        version=version,
        description=description,
        author=author,
        type=ptype,
        source_path=source_path,
        hardware=hardware_spec,
        extension=extension_spec,
    )


def _parse_detect(raw: dict, fname: str) -> DetectSpec:
    usb_list: list[UsbId] = []
    raw_usb = raw.get('usb', raw.get('usb_ids'))
    if raw_usb is not None:
        if not isinstance(raw_usb, list):
            raise PluginValidationError(fname, 'hardware.detect.usb must be a list')
        for idx, entry in enumerate(raw_usb):
            if not isinstance(entry, dict):
                raise PluginValidationError(
                    fname, f'hardware.detect.usb[{idx}] must be a mapping'
                )
            if 'vendor' not in entry:
                raise PluginValidationError(
                    fname, f'hardware.detect.usb[{idx}].vendor is required'
                )
            try:
                vendor = _parse_vendor_product(entry['vendor'])
            except ValueError as exc:
                raise PluginValidationError(
                    fname, f'hardware.detect.usb[{idx}].vendor: {exc}'
                ) from exc
            product: int | None = None
            if 'product' in entry and entry['product'] is not None:
                try:
                    product = _parse_vendor_product(entry['product'])
                except ValueError as exc:
                    raise PluginValidationError(
                        fname, f'hardware.detect.usb[{idx}].product: {exc}'
                    ) from exc
            usb_list.append(UsbId(vendor=vendor, product=product))

    executables: list[str] = []
    raw_exec = raw.get('executables')
    if raw_exec is not None:
        if not isinstance(raw_exec, list) or not all(
            isinstance(e, str) and e.strip() for e in raw_exec
        ):
            raise PluginValidationError(
                fname, 'hardware.detect.executables must be a list of non-empty strings'
            )
        executables = [e.strip() for e in raw_exec]

    system_vendor: str | None = None
    raw_sv = raw.get('system_vendor')
    if raw_sv is not None:
        if not isinstance(raw_sv, str) or not raw_sv.strip():
            raise PluginValidationError(
                fname,
                'hardware.detect.system_vendor must be a non-empty string if present',
            )
        system_vendor = raw_sv.strip()

    if not usb_list and not executables and not system_vendor:
        raise PluginValidationError(
            fname,
            'hardware.detect must define at least one of: usb, executables, system_vendor',
        )

    return DetectSpec(
        usb=usb_list, executables=executables, system_vendor=system_vendor
    )
