import argparse
from typing import Any, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ._version import __version__
from .globs import Globs
from .hardware import get_all_hardware, hardware

console = Console()


class VersionAction(argparse.Action):
    """Custom argparse action that prints the version and exits."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        console.print(f"[bold blue]BeatBoard[/bold blue] [cyan]{__version__}[/cyan]")
        parser.exit()


class HardwareAction(argparse.Action):
    """Custom argparse action that stores hardware options.

    Validation is deferred until after plugins are loaded in beatboard_main,
    so community drivers from ~/.config/beatboard/plugins are accepted.
    """

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        if values is None:
            values = []
        elif isinstance(values, str):
            values = [values]
        # Store raw values; validation happens after plugin load in beatboard_main
        setattr(namespace, self.dest, values)


def _validate_hardware_or_exit(values: list[str] | None) -> None:
    """Validate hardware names against combined registry and exit with table if invalid."""
    if not values:
        return
    try:
        keys = list(get_all_hardware().keys())
    except Exception:
        keys = list(hardware.keys())
    invalid = [v for v in values if v not in keys]
    if invalid:
        console.print(
            "[red bold]Error:[/red bold] Invalid hardware option(s):",
            ", ".join(f"'{v}'" for v in invalid),
        )
        console.print("\n[bold blue]Available hardware options:[/bold blue]")
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Hardware", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Source", style="dim")
        for key in sorted(keys):
            src = "builtin" if key in hardware else "plugin"
            table.add_row(
                key, f"Controls {key.upper()} keyboard RGB (Linux/Windows)", src
            )
        console.print(table)
        # Use parser to exit with code 1
        import sys

        sys.exit(1)


class DebugAction(argparse.Action):
    """Custom argparse action that validates debug categories and displays available categories if invalid."""

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: str | Sequence[Any] | None,
        option_string: str | None = None,
    ) -> None:
        if values is None:
            values = []
        elif isinstance(values, str):
            values = [values]

        valid_categories = {
            "command",
            "palette",
            "cache",
            "perf",
            "api",
            "plugins",
            "all",
        }
        invalid = [v for v in values if v not in valid_categories]

        if invalid:
            console.print(
                "[red bold]Error:[/red bold] Invalid debug category(ies):",
                ", ".join(f"'{v}'" for v in invalid),
            )
            console.print("\n[bold yellow]Available debug categories:[/bold yellow]")
            table = Table(show_header=True, header_style="bold yellow")
            table.add_column("Category", style="cyan")
            table.add_column("Description", style="white")
            descriptions = {
                "command": "Enable command debug logging",
                "palette": "Enable palette debug logging",
                "cache": "Enable cache debug logging",
                "perf": "Enable performance timing debug logging",
                "api": "Enable Spotify API debug logging (used when playerctl unavailable)",
                "plugins": "Enable plugin loading debug logging",
                "all": "Enable all debug logging",
            }
            for category in sorted(valid_categories):
                table.add_row(
                    category,
                    descriptions.get(category, f"Enable {category} debug logging"),
                )
            console.print(table)
            parser.exit(1)

        setattr(namespace, self.dest, values)


class RichArgumentParser(argparse.ArgumentParser):
    """Custom ArgumentParser that uses Rich for formatted help output."""

    def print_help(self, file=None):
        console.print(
            Panel.fit(
                f"[bold blue]BeatBoard[/bold blue] [cyan]v{__version__}[/cyan]\n[white]Change your hardware RGB based on music[/white]",
                border_style="blue",
            )
        )

        # Build options table
        table = Table(show_header=True, header_style="bold blue")
        table.add_column("Option", style="cyan")
        table.add_column("Description", style="white")

        for action in self._actions:
            if action.option_strings:
                opts = ", ".join(action.option_strings)
                table.add_row(opts, action.help or "")

        console.print(table)
        console.print()  # newline


# Create the parser
parser = RichArgumentParser(
    description="BeatBoard change your keyboard RGB based on music (Linux & Windows)",
)

parser.add_argument(
    "-v",
    "--version",
    action=VersionAction,
    nargs=0,
    help="Show the version number and exit",
)

parser.add_argument("-1", "--once", action="store_true", help="run once")

# hardware to change the color of
hardware_keys = list(hardware.keys())
parser.add_argument(
    "-H",
    "--hardware",
    action=HardwareAction,
    nargs="+",
    default=None,
    help=(
        "List of hardware to change the color of. "
        "Automatically detected on Linux when omitted. "
        "On macOS/Windows, manual specification recommended.\n"
        f"Built-ins: {', '.join(hardware_keys)}. "
        "Community drivers from ~/.config/beatboard/plugins/*.yaml are also available (see docs/plugins.md)."
    ),
)

parser.add_argument(
    "--refresh-hardware",
    action="store_true",
    default=False,
    help="Force re-detection of hardware and refresh cache",
)

parser.add_argument(
    "--reset-cache",
    action="store_true",
    default=False,
    help="Clear color cache only before starting (keeps hardware cache)",
)

debug_keys = list(Globs.debug.keys())
parser.add_argument(
    "-d",
    "--debug",
    action=DebugAction,
    nargs="*",
    metavar="CATEGORY",
    default=[],
    help=(f"Enable debug logging for specified categories:\n{', '.join(debug_keys)}"),
)

parser.add_argument(
    "--api",
    action="store_true",
    default=False,
    help="Use Spotify WebSocket API (required on platforms without playerctl)",
)
