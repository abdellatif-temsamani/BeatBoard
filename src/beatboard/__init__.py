import asyncio
from pathlib import Path

from rich import print

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
    and starts the playerctl watching process.
    """
    args = parser.parse_args()
    resolved_config_path = config_path or get_config_path()
    try:
        config = load_config(resolved_config_path)
    except (ConfigError, OSError) as error:
        print(
            f"[red bold]Error:[/red bold] Invalid configuration "
            f"at {resolved_config_path}: {error}"
        )
        return

    globs = Globs()
    # Cache path is strictly from config (with auto defaults); no :memory: fallback.
    globs.cache_path = config.cache_path or get_cache_db()
    Path(globs.cache_path).expanduser().parent.mkdir(parents=True, exist_ok=True)

    globs.debug = {
        "command": False,
        "palette": False,
        "cache": False,
        "perf": False,
        "api": False,
        "all": False,
    }
    all_keys: list[str] = list(globs.debug.keys())
    for category in [*config.debug, *args.debug]:
        if category == "all":
            for k in all_keys:
                globs.debug[k] = True  # type: ignore[index]
        else:
            globs.debug[category] = True  # type: ignore[index]

    # Spotify pure-websocket globals from config + CLI flags
    globs.config_path = resolved_config_path
    globs.spotify_token = config.spotify_token
    globs.spotify_refresh_token = config.spotify_refresh_token
    globs.spotify_client_id = config.spotify_client_id
    globs.spotify_client_secret = config.spotify_client_secret
    globs.spotify_redirect_uri = config.spotify_redirect_uri
    globs.spotify_websocket_url = config.spotify_websocket_url
    globs.api = bool(getattr(args, "api", False))

    source_migrations()

    # Hardware resolution: explicit CLI overrides, otherwise cache db, otherwise detect.
    # --refresh-hardware forces re-detection even when cache exists.
    selected_hardware = args.hardware
    if selected_hardware is None:
        # Use refresh flag to bypass cache
        if args.refresh_hardware:
            detected = detect_hardware()
            if not detected:
                print(
                    "[red bold]Error:[/red bold] No supported hardware detected. "
                    "Connect a supported device or select one with --hardware."
                )
                return
            print("[green bold]Detected hardware:[/green bold] " + ", ".join(detected))
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
            if cached:
                selected_hardware = cached
            else:
                detected = detect_hardware()
                if not detected:
                    print(
                        "[red bold]Error:[/red bold] No supported hardware detected. "
                        "Connect a supported device or select one with --hardware."
                    )
                    return
                print(
                    "[green bold]Detected hardware:[/green bold] " + ", ".join(detected)
                )
                try:
                    set_cached_hardware(detected)
                except Exception:
                    pass
                selected_hardware = detected

    if not selected_hardware:
        print(
            "[red bold]Error:[/red bold] No supported hardware detected. "
            "Connect a supported device or select one with --hardware."
        )
        return

    globs.hardware = selected_hardware

    use_api = bool(getattr(args, "api", False))

    if use_api:
        if not check_spotify_api_available():
            return
        await watch_spotify_api(args.once)
    else:
        if not check_spotify_available():
            print(
                "[red bold]Error:[/red bold] Spotify app not found. Please ensure Spotify is installed and running."
            )
            return

        await watch_playerctl(args.once)


def main():
    """Synchronous wrapper for the async main function."""
    try:
        asyncio.run(beatboard_main())
    except KeyboardInterrupt:
        print("\nShutting down...")
