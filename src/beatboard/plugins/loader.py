from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .errors import PluginError, PluginValidationError
from .models import Plugin, validate_plugin_dict

log = logging.getLogger('beatboard.plugins')

DEFAULT_PLUGIN_DIR = Path.home() / '.config' / 'beatboard' / 'plugins'


def get_plugin_dir(config_plugin_dir: str | None = None) -> Path | None:
    """Resolve plugin directory.

    Args:
        config_plugin_dir: Value from Config.plugin_dir (already expanded). If None, plugins disabled.
    Returns:
        Path or None if disabled.
    """
    if config_plugin_dir is None:
        return None
    # Empty handled in config, but guard
    if not config_plugin_dir.strip():
        return None
    return Path(config_plugin_dir).expanduser()


def discover_plugin_files(plugin_dir: Path) -> list[Path]:
    """Return sorted list of yaml files in plugin_dir."""
    if not plugin_dir.is_dir():
        return []
    files: list[Path] = []
    for pattern in ('*.yaml', '*.yml'):
        files.extend(plugin_dir.glob(pattern))
    # Also include subdirs one level? For now only top level. Sort deterministic.
    return sorted(files)


def load_plugin_file(path: Path) -> Plugin:
    """Load a single YAML plugin file, validating it.

    Raises PluginError on failure.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as exc:
        raise PluginError(f'{path}: cannot read file: {exc}') from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise PluginValidationError(str(path), f'invalid YAML: {exc}') from exc
    if data is None:
        raise PluginValidationError(str(path), 'file is empty')
    return validate_plugin_dict(data, path)


def load_plugins(
    plugin_dir: Path | str | None,
    *,
    strict: bool = False,
) -> tuple[dict[str, Plugin], list[PluginError]]:
    """Discover and load plugins from plugin_dir.

    Args:
        plugin_dir: Directory path or None (disabled). String will be expanded.
        strict: If True, raise on first error. Otherwise collect errors and skip invalid files.

    Returns:
        (plugins_by_name, errors) where plugins_by_name maps name -> Plugin.

    Side effects:
        Does NOT auto-register into hardware registry. Caller should call
        ``register_plugins`` or handle registration.

    """
    errors: list[PluginError] = []
    plugins: dict[str, Plugin] = {}

    if plugin_dir is None:
        return plugins, errors

    if isinstance(plugin_dir, str):
        if not plugin_dir.strip():
            return plugins, errors
        dir_path = Path(plugin_dir).expanduser()
    else:
        dir_path = Path(plugin_dir).expanduser()

    # Ensure directory exists (create if missing for default location)
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        err = PluginError(f'{dir_path}: cannot create plugin dir: {exc}')
        if strict:
            raise err from exc
        errors.append(err)
        return plugins, errors

    files = discover_plugin_files(dir_path)
    for f in files:
        try:
            plugin = load_plugin_file(f)
        except PluginError as exc:
            if strict:
                raise
            errors.append(exc)
            # Log gracefully
            try:
                from rich import print as rprint

                rprint(f'[yellow]Warning:[/yellow] Skipping plugin {f.name}: {exc}')
            except Exception:
                print(f'Warning: Skipping plugin {f.name}: {exc}')
            continue

        if plugin.name in plugins:
            err = PluginValidationError(
                str(f),
                f"duplicate plugin name '{plugin.name}' already loaded from {plugins[plugin.name].source_path}",
            )
            if strict:
                raise err
            errors.append(err)
            try:
                from rich import print as rprint

                rprint(
                    f"[yellow]Warning:[/yellow] Duplicate plugin name '{plugin.name}' in {f.name}, skipping"
                )
            except Exception:
                print(
                    f"Warning: Duplicate plugin name '{plugin.name}' in {f.name}, skipping"
                )
            continue

        plugins[plugin.name] = plugin

    return plugins, errors


def register_plugins(plugins: dict[str, Plugin]) -> tuple[int, list[str]]:
    """Register hardware plugins into the global hardware registry.

    Returns (registered_count, skipped_names).

    For extension plugins, this currently just counts them but does not
    execute hooks. Extension registry is kept in memory for future use.
    """
    # Lazy import to avoid circular
    from beatboard import hardware as hw_module

    registered = 0
    skipped: list[str] = []
    for name, plugin in plugins.items():
        if plugin.type == 'hardware' and plugin.hardware is not None:
            try:
                hw_module.register_plugin_hardware(
                    name, plugin.hardware.command, plugin.hardware.detect
                )
                registered += 1
            except ValueError as exc:
                skipped.append(name)
                try:
                    from rich import print as rprint

                    rprint(
                        f"[yellow]Warning:[/yellow] Skipping hardware plugin '{name}': {exc}"
                    )
                except Exception:
                    print(f"Warning: Skipping hardware plugin '{name}': {exc}")
        elif plugin.type == 'extension':
            # Keep extension plugins in a separate registry
            try:
                from beatboard.plugins.registry import extension_registry

                extension_registry[name] = plugin
                registered += 1
            except Exception:
                # Fallback import
                registered += 1
        else:
            skipped.append(name)
    return registered, skipped
