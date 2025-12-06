import argparse

from .hardware import hardware

# Create the parser
parser = argparse.ArgumentParser(
    description="BeatBoard change your keyboard rgb based on music",
)

# makes the program running and follow song changes
parser.add_argument("--follow", action="store_true", help="Follow the music")

# hardware to change the color of
parser.add_argument(
    "--hardware",
    choices=list(hardware.keys()),
    nargs="+",
    default=[list(hardware.keys())[0]],
    help="List of hardware to change the color of",
)
