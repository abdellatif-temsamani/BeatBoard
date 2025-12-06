import argparse

parser = argparse.ArgumentParser(
    description="BeatBoard change your keyboard rgb based on music",
)

parser.add_argument("--follow", action="store_true", help="Follow the music")

parser.add_argument(
    "--keyboard", choices=["g213"], default="g213", help="Keyboard to use"
)
