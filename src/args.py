import argparse
import tomllib
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .hardware import hardware

# Read version from pyproject.toml
pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
with open(pyproject_path, "rb") as f:
    pyproject_data = tomllib.load(f)
__version__ = pyproject_data["project"]["version"]

console = Console()


class VersionAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        console.print(f"[bold blue]BeatBoard[/bold blue] [cyan]{__version__}[/cyan]")
        parser.exit()


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

# makes the program running and follow song changes
parser.add_argument("--follow", action="store_true", help="Follow the music")
parser.add_argument("--debug", action="store_true", help="Enable debug mode")

# hardware to change the color of
parser.add_argument(
    "--hardware",
    choices=list(hardware.keys()),
    nargs="+",
    default=[list(hardware.keys())[0]],
    help="List of hardware to change the color of",
)
