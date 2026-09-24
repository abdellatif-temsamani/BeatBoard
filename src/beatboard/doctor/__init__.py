"""Doctor – orchestrates BeatBoard diagnostics.

Public facade: run_doctor() is called from beatboard_main when --doctor is set.
Each domain (config, cache, permissions, hardware, spotify, openrgb, system)
lives in its own submodule to respect single-responsibility and 400-line soft limit.
"""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .cache import diagnose_cache
from .config import diagnose_config
from .hardware import diagnose_hardware
from .openrgb import diagnose_openrgb
from .permissions import diagnose_permissions
from .spotify import diagnose_spotify
from .system import diagnose_system


def _status_style(status: str) -> tuple[str, str]:
    """Map status to (icon, style)."""
    s = status.lower()
    if s == 'ok':
        return '✔', 'green'
    if s == 'warn':
        return '!', 'yellow'
    if s == 'fail':
        return '✘', 'red'
    return '•', 'dim'


def _render_section(console: Console, title: str, results: list[dict[str, str]]) -> int:
    """Render a section table, return count of fails."""
    table = Table(
        show_header=True,
        header_style='bold blue',
        expand=False,
        box=None,
        padding=(0, 1),
    )
    table.add_column('Status', width=6, justify='center')
    table.add_column('Check', style='cyan', no_wrap=False)
    table.add_column('Detail', style='white', no_wrap=False)
    table.add_column('Hint', style='dim', no_wrap=False)

    fails = 0
    warns = 0
    for r in results:
        icon, style = _status_style(r.get('status', 'info'))
        check = r.get('check', '')
        detail = r.get('detail', '')
        hint = r.get('hint', '')
        # Truncate very long details for readability
        if len(detail) > 120:
            detail = detail[:117] + '...'
        if len(hint) > 80:
            hint = hint[:77] + '...'
        table.add_row(f'[{style}]{icon}[/{style}]', check, detail, hint)
        if r.get('status') == 'fail':
            fails += 1
        elif r.get('status') == 'warn':
            warns += 1

    # Section header with summary
    summary = f'{len(results)} checks'
    if fails:
        summary += f' • [red]{fails} fail[/red]'
    if warns:
        summary += f' • [yellow]{warns} warn[/yellow]'
    console.print(
        Panel(
            table,
            title=f'[bold blue]{title}[/bold blue]  [dim]({summary})[/dim]',
            border_style='blue',
            padding=(0, 1),
        )
    )
    return fails


def run_doctor(
    config_path: Path | None = None,
    *,
    cache_path_str: str | None = None,
    console: Console | None = None,
    exit_on_complete: bool = False,
) -> int:
    """Run all diagnostics and render report.

    Args:
        config_path: Optional path to config.yaml. If None, uses get_config_path().
        cache_path_str: Optional cache path override (for tests). If None, resolved from Globs/config.
        console: Optional Rich Console for tests.
        exit_on_complete: If True, sys.exit after report.

    Returns:
        int: 0 if no failures, 1 if any check failed.
    """
    con = console or Console()
    # Header
    try:
        from beatboard._version import __version__

        ver = __version__
    except Exception:
        ver = 'unknown'

    con.print(
        Panel.fit(
            f'[bold blue]BeatBoard Doctor[/bold blue]  [cyan]v{ver}[/cyan]\n[white]Diagnose Spotify, permissions, hardware, OpenRGB, cache, config[/white]',
            border_style='blue',
        )
    )

    # Resolve paths early for downstream modules
    if config_path is None:
        try:
            from beatboard.config import get_config_path

            config_path = get_config_path()
        except Exception:
            config_path = Path.home() / '.config' / 'beatboard' / 'config.yaml'

    if cache_path_str is None:
        try:
            from beatboard.globs import Globs

            cache_path_str = Globs().cache_path
            if not cache_path_str:
                from beatboard.globs import get_cache_db

                cache_path_str = get_cache_db()
        except Exception:
            cache_path_str = str(
                Path.home() / '.local' / 'state' / 'beatboard' / 'cache.db'
            )
        # Prefer config's cache_path if available and Globs still default
        try:
            if config_path and config_path.is_file():
                try:
                    # Avoid healing during doctor read – just parse raw yaml for cache_path
                    import yaml

                    data = yaml.safe_load(config_path.read_text(encoding='utf-8')) or {}
                    if isinstance(data, dict) and data.get('cache_path'):
                        cp = data.get('cache_path')
                        if isinstance(cp, str) and cp.strip():
                            cache_path_str = str(Path(cp).expanduser())
                except Exception:
                    pass
        except Exception:
            pass

    total_fails = 0
    detected_hardware: list[str] = []

    # Detect hardware early for dynamic permission checks
    try:
        from beatboard.hardware import detect_hardware

        detected_hardware = detect_hardware()
    except Exception:
        detected_hardware = []

    # Each section isolated so one failure doesn't abort others
    sections: list[tuple[str, callable]] = [
        ('System', lambda: diagnose_system()),
        ('Config', lambda: diagnose_config(config_path)),
        ('Cache', lambda: diagnose_cache(cache_path_str)),
        ('Hardware', lambda: diagnose_hardware()),
        (
            'Permissions',
            lambda: diagnose_permissions(
                config_path, cache_path_str, detected_hardware
            ),
        ),
        ('Spotify', lambda: diagnose_spotify()),
        ('OpenRGB', lambda: diagnose_openrgb()),
    ]

    for title, fn in sections:
        try:
            results = fn()
        except Exception as exc:
            results = [
                {
                    'check': title + ' diagnostics',
                    'status': 'fail',
                    'detail': str(exc),
                    'hint': 'See traceback with --debug',
                }
            ]
        fails = _render_section(con, title, results)
        total_fails += fails
        con.print()  # spacer

    # Overall summary
    if total_fails == 0:
        con.print(
            Panel(
                '[green bold]All critical checks passed[/green bold] • review [yellow]warn[/yellow]/[dim]info[/dim] hints above',
                border_style='green',
            )
        )
    else:
        con.print(
            Panel(
                f'[red bold]{total_fails} critical failure(s) found[/red bold] – see hints above',
                border_style='red',
            )
        )
        # Print common fixes
        fixes = Text()
        fixes.append('Common fixes:\n', style='bold')
        fixes.append('• Config: ', style='cyan')
        fixes.append('edit ~/.config/beatboard/config.yaml\n', style='white')
        fixes.append('• Cache: ', style='cyan')
        fixes.append(
            'beatboard --reset-cache  or  rm ~/.local/state/beatboard/cache.db\n',
            style='white',
        )
        fixes.append('• Permissions (Linux): ', style='cyan')
        fixes.append(
            'sudo usermod -a -G input $USER  + re-login; check udev\n', style='white'
        )
        fixes.append('• Hardware: ', style='cyan')
        fixes.append(
            'beatboard --hardware g213  or  install razer-cli/asusctl\n', style='white'
        )
        fixes.append('• Spotify API: ', style='cyan')
        fixes.append(
            'create app at https://developer.spotify.com/dashboard, set client_id/secret, run beatboard --api\n',
            style='white',
        )
        fixes.append('• OpenRGB: ', style='cyan')
        fixes.append(
            'install OpenRGB and enable SDK Server (port 6742) if you need generic RGB\n',
            style='white',
        )
        con.print(Panel(fixes, border_style='yellow', title='Fix Suggestions'))

    con.print(
        f'[dim]Doctor run complete – config: {config_path}  cache: {cache_path_str}  python: {sys.version.split()[0]}[/dim]'
    )

    if exit_on_complete:
        import sys as _sys

        _sys.exit(1 if total_fails else 0)
    return 1 if total_fails else 0


__all__ = ['run_doctor']
