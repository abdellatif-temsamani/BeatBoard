import argparse

# Read version from package metadata
from importlib.metadata import version
from typing import Any, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .globs import Globs
from .hardware import hardware

__version__ = version("beatboard")

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
    """Custom argparse action that validates hardware options and displays available hardware if invalid."""

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
            for key in keys:
                table.add_row(key, f"Controls {key.upper()} keyboard RGB")
            console.print(table)
            parser.exit(1)

        setattr(namespace, self.dest, values)


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

        valid_categories = {"command", "palette", "cache"}
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
            for category in sorted(valid_categories):
                table.add_row(category, f"Enable {category} debug logging")
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
        console.print()  # newlin


# Create the parser
parser = RichArgumentParser(
    description="BeatBoard change your keyboard rgb based on music",
)

parser.add_argument(
    "-v",
    "--version",
    action=VersionAction,
    nargs=0,
    help="Show the version number and exit",
)

parser.add_argument("-f", "--follow", action="store_true", help="Follow the music")

# hardware to change the color of
hardware_keys = list(hardware.keys())
parser.add_argument(
    "-H",
    "--hardware",
    action=HardwareAction,
    nargs="+",
    default=[hardware_keys[0]],
    help=(f"List of hardware to change the color of:\n{', '.join(hardware_keys)}"),
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
