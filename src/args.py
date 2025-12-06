import argparse

from .hardware import hardware

# Create the parser
parser = argparse.ArgumentParser(
    description="BeatBoard change your keyboard rgb based on music",
)

# makes the program running and follow song changes
parser.add_argument("--follow", action="store_true", help="Follow the music")

parser.add_argument(
    "--hardware",
    choices=list(hardware.keys()),
    nargs="+",  # allow one or more values
    default=[list(hardware.keys())[0]],
    help="Hardware to use",
)
