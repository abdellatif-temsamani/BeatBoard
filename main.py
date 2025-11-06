#!/usr/bin/env python3

import subprocess

IMAGE_PATH = "/tmp/album_art.jpg"


def get_image() -> None:

    import requests

    url = subprocess.run(
        ["playerctl", "metadata", "mpris:artUrl"],
        capture_output=True,
        text=True,
    )

    url = url.stdout.strip()

    if url.startswith("file://"):
        path = url[7:]  # remove 'file://'
        with open(path, "rb") as f:
            image_data = f.read()
    else:
        # Download via HTTP(S)
        response = requests.get(url)
        response.raise_for_status()  # ensure we got the file
        image_data = response.content

    # Save to a local file
    with open(IMAGE_PATH, "wb") as f:
        f.write(image_data)


def get_color_palette() -> list[str]:
    from colorthief import ColorThief

    ct = ColorThief(IMAGE_PATH)

    palette = ct.get_palette(color_count=10)

    # NOTE: for debugging purposes
    # import matplotlib.pyplot as plt
    #
    # plt.imshow([[palette[i] for i in range(9)]])
    # plt.show()

    colors = []
    for color in palette:
        colors.append(f"{color[0]:02x}{color[1]:02x}{color[2]:02x}")

    return colors


if __name__ == "__main__":

    image = get_image()
    colors = get_color_palette()

    subprocess.run(["python", "./G213Colors/G213Colors.py", "-c", colors[2]])
    # print(colors)
