import asyncio
import sys
from pathlib import Path

from rich import print

from ._version import __version__ as __version__  # noqa: F401 - re-exported
from .args import parser
from .cache.db import get_cached_hardware, set_cached_hardware, source_migrations
from .config import ConfigError, get_config_path, load_config
from .globs import Globs, get_cache_db
from .hardware import detect_hardware
from .playerctl import check_spotify_available, watch_playerctl
from .spotify import (
    check_spotify_api_available,
    get_spotify_token,  # noqa: F401 - re-exported for tests / external use
    watch_spotify_api,
)


async def beatboard_main(config_path: Path | None = None):
    """
    Main entry point for BeatBoard.

    Parses command-line arguments, sets up global state,
    loads community plugins, and starts the playerctl watching process.
    """
    resolved_config_path = config_path or get_config_path()
    # Fast peek for --doctor so invalid config can still be diagnosed
    _is_doctor_argv = '--doctor' in sys.argv
    try:
        config = load_config(resolved_config_path)
    except (ConfigError, OSError) as error:
        if _is_doctor_argv:
            # Still run doctor to diagnose the bad config
            try:
                from .doctor import run_doctor

                # Initialize globs minimally so other sections can still run
                _gl = Globs()
                # Use defaults for cache/plugin when config failed
                try:
                    _gl.cache_path = get_cache_db()
                except Exception:
                    pass
                run_doctor(resolved_config_path)
            except Exception as doc_exc:
                print(f'[red bold]Doctor failed:[/red bold] {doc_exc}')
            print(
                f'[red bold]Error:[/red bold] Invalid configuration '
                f'at {resolved_config_path}: {error}'
            )
            return
        print(
            f'[red bold]Error:[/red bold] Invalid configuration '
            f'at {resolved_config_path}: {error}'
        )
        return

    globs = Globs()
    # Cache path is strictly from config (with auto defaults); no :memory: fallback.
    globs.cache_path = config.cache_path or get_cache_db()
    Path(globs.cache_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    # Plugin dir – default ~/.config/beatboard/plugins (user can change in config)
    globs.plugin_dir = config.plugin_dir

    # Parse CLI args first (HardwareAction is now non-validating, so plugins can be validated after load)
    args = parser.parse_args()

    # --doctor: run diagnostics and exit (after config + args, before hardware init)
    if getattr(args, 'doctor', False):
        # Ensure globs are populated for doctor submodules (spotify, etc.)
        globs.config_path = resolved_config_path
        globs.spotify_token = config.spotify_token
        globs.spotify_refresh_token = config.spotify_refresh_token
        globs.spotify_client_id = config.spotify_client_id
        globs.spotify_client_secret = config.spotify_client_secret
        globs.spotify_redirect_uri = config.spotify_redirect_uri
        globs.spotify_websocket_url = config.spotify_websocket_url
        # Load plugins briefly so hardware diagnostics see community drivers
        # (don't fail doctor if plugin load fails)
        try:
            from .hardware import clear_plugin_hardware
            from .plugins.loader import load_plugins, register_plugins
            from .plugins.registry import clear_extension_registry

            clear_plugin_hardware()
            clear_extension_registry()
            if globs.plugin_dir:
                _p_dir = Path(globs.plugin_dir).expanduser()
                _p_dir.mkdir(parents=True, exist_ok=True)
                plugins, _ = load_plugins(_p_dir)
                if plugins:
                    register_plugins(plugins)
        except Exception:
            pass
        try:
            from .doctor import run_doctor

            run_doctor(resolved_config_path, cache_path_str=globs.cache_path)
        except Exception as exc:
            print(f'[red bold]Doctor failed:[/red bold] {exc}')
        return

    # Combine debug from config and CLI — do this before plugin loading so -d plugins is visible
    globs.debug = {
        'command': False,
        'palette': False,
        'cache': False,
        'perf': False,
        'api': False,
        'plugins': False,
        'all': False,
    }
    for category in config.debug:
        if category == 'all':
            for k in list(globs.debug.keys()):
                globs.debug[k] = True  # type: ignore[index]
        else:
            globs.debug[category] = True  # type: ignore[index]
    all_keys: list[str] = list(globs.debug.keys())
    for category in args.debug:
        if category == 'all':
            for k in all_keys:
                globs.debug[k] = True  # type: ignore[index]
        else:
            globs.debug[category] = True  # type: ignore[index]

    # Load community plugins (YAML manifests). Errors are warnings, not fatal.
    # Clear previous plugin registrations to support reloads (e.g., tests calling beatboard_main twice)
    try:
        from .args import _validate_hardware_or_exit
        from .hardware import clear_plugin_hardware
        from .plugins.loader import load_plugins, register_plugins
        from .plugins.registry import clear_extension_registry

        clear_plugin_hardware()
        clear_extension_registry()

        if globs.plugin_dir:
            p_dir = Path(globs.plugin_dir).expanduser()
            # Ensure directory exists for fresh installs
            try:
                p_dir.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
            plugins, plugin_errors = load_plugins(p_dir)
            if globs.debug.get('plugins') or globs.debug.get('all'):
                print(
                    f'[dim]plugins: scanning {p_dir} — found {len(plugins)} plugin(s), {len(plugin_errors)} error(s)[/dim]'
                )
            if plugins:
                registered, _ = register_plugins(plugins)
                if globs.debug.get('plugins') or globs.debug.get('all'):
                    print(f'[dim]plugins loaded: {registered} from {p_dir}[/dim]')
                    for name, p in plugins.items():
                        print(
                            f'[dim]  • {name} ({p.type}) v{p.version} from {p.source_path.name}[/dim]'
                        )
                elif registered and (
                    globs.debug.get('cache') or globs.debug.get('all')
                ):
                    print(f'[dim]plugins loaded: {registered} from {p_dir}[/dim]')
            else:
                if globs.debug.get('plugins') or globs.debug.get('all'):
                    print('[dim]plugins: no community plugins found[/dim]')
            # plugin_errors are already warned inside loader
        else:
            if globs.debug.get('plugins') or globs.debug.get('all'):
                print('[dim]plugins: disabled (plugin_dir is null)[/dim]')
        # Validate hardware names now that plugins are loaded (HardwareAction was non-validating)
        _validate_hardware_or_exit(getattr(args, 'hardware', None))
    except SystemExit:
        raise
    except Exception as exc:
        print(f'[yellow]Warning:[/yellow] plugin loading failed: {exc}')

    # Spotify pure-websocket globals from config + CLI flags
    globs.config_path = resolved_config_path
    globs.spotify_token = config.spotify_token
    globs.spotify_refresh_token = config.spotify_refresh_token
    globs.spotify_client_id = config.spotify_client_id
    globs.spotify_client_secret = config.spotify_client_secret
    globs.spotify_redirect_uri = config.spotify_redirect_uri
    globs.spotify_websocket_url = config.spotify_websocket_url
    globs.api = bool(getattr(args, 'api', False))

    # Handle --reset-cache: clear color cache only (keep hardware)
    if getattr(args, 'reset_cache', False):
        from .cache.db import reset_cache

        reset_cache()
        if (
            globs.debug.get('cache')
            or globs.debug.get('plugins')
            or globs.debug.get('all')
        ):
            print(f'[dim]color cache reset: {globs.cache_path}[/dim]')
        else:
            print('[green]Color cache reset[/green]')

    source_migrations()

    # Hardware resolution: explicit CLI overrides, otherwise cache db, otherwise detect.
    # --refresh-hardware forces re-detection even when cache exists.
    selected_hardware = args.hardware
    if selected_hardware is None:
        # Use refresh flag to bypass cache
        if args.refresh_hardware:
            detected = detect_hardware()
            if globs.debug.get('cache') or globs.debug.get('all'):
                print(f'[dim]detect --refresh: detected={detected}[/dim]')
            if not detected:
                if globs.debug.get('cache') or globs.debug.get('all'):
                    print(
                        '[dim]no hardware detected — continuing without hardware[/dim]'
                    )
                detected = []
            if detected:
                print(
                    '[green bold]Detected hardware:[/green bold] ' + ', '.join(detected)
                )
            try:
                set_cached_hardware(detected)
            except Exception:
                pass
            selected_hardware = detected
        else:
            try:
                cached = get_cached_hardware()
            except Exception:
                cached = []
            if globs.debug.get('cache') or globs.debug.get('all'):
                print(f'[dim]cache: hardware cached={cached}[/dim]')
            if cached:
                selected_hardware = cached
            else:
                detected = detect_hardware()
                if globs.debug.get('cache') or globs.debug.get('all'):
                    from .hardware import get_all_hardware

                    print(
                        f'[dim]detect: hardware={list(get_all_hardware().keys())} detected={detected}[/dim]'
                    )
                if not detected:
                    if globs.debug.get('all'):
                        import shutil

                        print(
                            f'[dim]debug: razer-cli={shutil.which("razer-cli")} asusctl={shutil.which("asusctl")} is_windows={__import__("beatboard.hardware", fromlist=["is_windows"]).is_windows()}[/dim]'
                        )
                    if globs.debug.get('cache') or globs.debug.get('all'):
                        print(
                            '[dim]no hardware detected — continuing without hardware[/dim]'
                        )
                    detected = []
                if detected:
                    print(
                        '[green bold]Detected hardware:[/green bold] '
                        + ', '.join(detected)
                    )
                    try:
                        set_cached_hardware(detected)
                    except Exception:
                        pass
                selected_hardware = detected

    # Fallback to config hardware when autodetection yields nothing
    # (e.g., laptop internal keyboards not visible via USB/DMI)
    _cfg_hw_raw = getattr(config, 'hardware', None)
    # Don't validate fallback here; only validate when actually needed
    # so invalid fallback doesn't break runs where detection succeeds.
    _fallback_hw: list[str] | None = (
        list(_cfg_hw_raw) if _cfg_hw_raw else None  # type: ignore[arg-type]
    )

    if not selected_hardware:
        if _fallback_hw:
            try:
                from .args import _validate_hardware_or_exit as _validate_fallback

                _validate_fallback(_fallback_hw)
            except SystemExit:
                raise
            except Exception as exc:  # pragma: no cover
                print(
                    f'[yellow]Warning:[/yellow] invalid fallback hardware in config: {exc}'
                )
                _fallback_hw = None
            if _fallback_hw:
                selected_hardware = _fallback_hw
                if (
                    globs.debug.get('cache')
                    or globs.debug.get('all')
                    or globs.debug.get('plugins')
                ):
                    print(
                        f'[dim]using fallback hardware from config: {selected_hardware}[/dim]'
                    )
                else:
                    print(
                        f'[green]Using fallback hardware from config:[/green] {", ".join(selected_hardware)}'
                    )
                try:
                    set_cached_hardware(selected_hardware)
                except Exception:
                    pass
    elif _fallback_hw and args.hardware is None:
        # Handle config edit while cache holds stale fallback.
        # Only validate if we actually need to replace the stale cache.
        try:
            _cached_hw = get_cached_hardware()
        except Exception:
            _cached_hw = []
        if (
            _cached_hw
            and selected_hardware == _cached_hw
            and set(_cached_hw) != set(_fallback_hw)
        ):
            try:
                _fresh_detected = detect_hardware()
            except Exception:
                _fresh_detected = []
            if not _fresh_detected:
                try:
                    from .args import _validate_hardware_or_exit as _validate_fallback2

                    _validate_fallback2(_fallback_hw)  # type: ignore[arg-type]
                except SystemExit:
                    raise
                except Exception as exc:  # pragma: no cover
                    print(
                        f'[yellow]Warning:[/yellow] invalid fallback hardware in config: {exc}'
                    )
                    _fallback_hw = None  # type: ignore[assignment]
                if _fallback_hw:
                    selected_hardware = _fallback_hw
                    if (
                        globs.debug.get('cache')
                        or globs.debug.get('all')
                        or globs.debug.get('plugins')
                    ):
                        print(
                            f'[dim]using updated fallback hardware from config: {selected_hardware} (cache stale)[/dim]'
                        )
                    else:
                        print(
                            f'[green]Using fallback hardware from config:[/green] {", ".join(selected_hardware)}'
                        )
                    try:
                        set_cached_hardware(selected_hardware)
                    except Exception:
                        pass

    if not selected_hardware:
        if globs.debug.get('all'):
            print('[dim]no hardware selected — continuing without hardware[/dim]')
        # No hardware is not fatal — continue with empty hardware list (color extraction still runs)
        selected_hardware = []  # type: ignore[assignment]

    globs.hardware = selected_hardware

    use_api = bool(getattr(args, 'api', False))

    if use_api:
        if not check_spotify_api_available():
            return
        await watch_spotify_api(args.once)
    else:
        if not check_spotify_available():
            print(
                '[red bold]Error:[/red bold] Spotify app not found. Please ensure Spotify is installed and running.'
            )
            return

        await watch_playerctl(args.once)


def main():
    """Synchronous wrapper for the async main function."""
    try:
        asyncio.run(beatboard_main())
    except KeyboardInterrupt:
        print('\nShutting down...')
