import argparse

# Read version from package metadata
from importlib.metadata import version
from typing import Any, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .hardware import hardware

__version__ = version("beatboard")

console = Console()


class VersionAction(argparse.Action):
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


class RichArgumentParser(argparse.ArgumentParser):
    def print_help(self, file=None):
        console.print(
            Panel.fit(
                "[bold blue]BeatBoard[/bold blue]\n[white]Change your hardware RGB based on music[/white]",
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
    "--version", action=VersionAction, nargs=0, help="Show the version number and exit"
)

# hardware to change the color of
keys = list(hardware.keys())
parser.add_argument(
    "--hardware",
    action=HardwareAction,
    nargs="+",
    default=[keys[0]],
    help=(
        f"List of hardware to change the color of:\n"
        f"{''.join(', '.join(keys[i : i + 4]) for i in range(0, len(keys), 4))}"
    ),
)

# makes the program running and follow song changes
parser.add_argument("--follow", action="store_true", help="Follow the music")
parser.add_argument("--debug-command", action="store_true", help="Enable debug mode")
parser.add_argument("--debug-palette", action="store_true", help="Enable debug mode")
