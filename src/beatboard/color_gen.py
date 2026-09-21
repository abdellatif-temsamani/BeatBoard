"""Color extraction inspired by node-vibrant.

Palette generation follows similar quantization (modified median-cut) and
palette-selection ideas as https://github.com/Vibrant-Colors/node-vibrant
(MIT License, Copyright (c) 2015 Jari Zwarts and AKFish), but this is an
original implementation that does not contain code copied from that project.
"""

from __future__ import annotations

import colorsys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Sequence

from PIL import Image, ImageOps
from rich import print
from rich.color import Color
from rich.console import Console
from rich.style import Style
from rich.text import Text

from .globs import Globs

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]

_SIG_BITS = 5
_RSHIFT = 8 - _SIG_BITS
_FRACTION_BY_POPULATION = 0.75
COLOR_CACHE_VERSION = 'node-vibrant-v1'


@dataclass(eq=False, frozen=True)
class Swatch:
    """A quantized color and the number of source pixels it represents."""

    rgb: RGB
    population: int

    @property
    def hsl(self) -> tuple[float, float, float]:
        """Return hue, saturation, and lightness in the 0..1 range."""
        hue, lightness, saturation = colorsys.rgb_to_hls(
            *(channel / 255 for channel in self.rgb)
        )
        return hue, saturation, lightness

    @property
    def hex(self) -> str:
        """Return a six-character lowercase hex color without a prefix."""
        return _to_hex(self.rgb)


@dataclass(frozen=True)
class VibrantPalette:
    """The six color roles produced by node-vibrant's default generator."""

    vibrant: Swatch | None = None
    dark_vibrant: Swatch | None = None
    light_vibrant: Swatch | None = None
    muted: Swatch | None = None
    dark_muted: Swatch | None = None
    light_muted: Swatch | None = None

    def swatches(self) -> Iterator[Swatch]:
        """Yield distinct swatches in node-vibrant's primary-role order."""
        seen: set[RGB] = set()
        for swatch in (
            self.vibrant,
            self.dark_vibrant,
            self.light_vibrant,
            self.muted,
            self.dark_muted,
            self.light_muted,
        ):
            if swatch is not None and swatch.rgb not in seen:
                seen.add(swatch.rgb)
                yield swatch


@dataclass(frozen=True)
class _GeneratorOptions:
    target_dark_luma: float = 0.26
    max_dark_luma: float = 0.45
    min_light_luma: float = 0.55
    target_light_luma: float = 0.74
    min_normal_luma: float = 0.3
    target_normal_luma: float = 0.5
    max_normal_luma: float = 0.7
    target_muted_saturation: float = 0.3
    max_muted_saturation: float = 0.4
    target_vibrant_saturation: float = 1.0
    min_vibrant_saturation: float = 0.35
    weight_saturation: float = 3
    weight_luma: float = 6.5
    weight_population: float = 0.5


class _Histogram:
    """A 5-bit-per-channel histogram equivalent to node-vibrant's Histogram."""

    def __init__(self, pixels: Iterable[RGBA]) -> None:
        self.values = [0] * (1 << (3 * _SIG_BITS))
        self.rmin = self.gmin = self.bmin = 1 << _SIG_BITS
        self.rmax = self.gmax = self.bmax = 0
        self.color_count = 0

        for red, green, blue, alpha in pixels:
            if not _default_filter(red, green, blue, alpha):
                continue

            red >>= _RSHIFT
            green >>= _RSHIFT
            blue >>= _RSHIFT
            index = self.index(red, green, blue)
            if self.values[index] == 0:
                self.color_count += 1
            self.values[index] += 1
            self.rmin = min(self.rmin, red)
            self.rmax = max(self.rmax, red)
            self.gmin = min(self.gmin, green)
            self.gmax = max(self.gmax, green)
            self.bmin = min(self.bmin, blue)
            self.bmax = max(self.bmax, blue)

    @staticmethod
    def index(red: int, green: int, blue: int) -> int:
        return (red << (2 * _SIG_BITS)) + (green << _SIG_BITS) + blue


class _VBox:
    """A mutable RGB box used by modified median-cut quantization."""

    def __init__(
        self,
        r1: int,
        r2: int,
        g1: int,
        g2: int,
        b1: int,
        b2: int,
        histogram: _Histogram,
    ) -> None:
        self.dimension = {
            'r1': r1,
            'r2': r2,
            'g1': g1,
            'g2': g2,
            'b1': b1,
            'b2': b2,
        }
        self.histogram = histogram
        self._volume: int | None = None
        self._count: int | None = None
        self._average: RGB | None = None

    @classmethod
    def build(cls, histogram: _Histogram) -> _VBox:
        return cls(
            histogram.rmin,
            histogram.rmax,
            histogram.gmin,
            histogram.gmax,
            histogram.bmin,
            histogram.bmax,
            histogram,
        )

    def clone(self) -> _VBox:
        d = self.dimension
        return _VBox(
            d['r1'], d['r2'], d['g1'], d['g2'], d['b1'], d['b2'], self.histogram
        )

    def volume(self) -> int:
        if self._volume is None:
            d = self.dimension
            self._volume = (
                (d['r2'] - d['r1'] + 1)
                * (d['g2'] - d['g1'] + 1)
                * (d['b2'] - d['b1'] + 1)
            )
        return self._volume

    def count(self) -> int:
        if self._count is None:
            d = self.dimension
            values = self.histogram.values
            index = self.histogram.index
            self._count = sum(
                values[index(red, green, blue)]
                for red in range(d['r1'], d['r2'] + 1)
                for green in range(d['g1'], d['g2'] + 1)
                for blue in range(d['b1'], d['b2'] + 1)
            )
        return self._count

    def average(self) -> RGB:
        if self._average is not None:
            return self._average

        d = self.dimension
        values = self.histogram.values
        index = self.histogram.index
        multiplier = 1 << _RSHIFT
        total = red_sum = green_sum = blue_sum = 0

        for red in range(d['r1'], d['r2'] + 1):
            for green in range(d['g1'], d['g2'] + 1):
                for blue in range(d['b1'], d['b2'] + 1):
                    population = values[index(red, green, blue)]
                    if not population:
                        continue
                    total += population
                    red_sum += int(population * (red + 0.5) * multiplier)
                    green_sum += int(population * (green + 0.5) * multiplier)
                    blue_sum += int(population * (blue + 0.5) * multiplier)

        if total:
            self._average = (
                red_sum // total,
                green_sum // total,
                blue_sum // total,
            )
        else:
            self._average = (
                multiplier * (d['r1'] + d['r2'] + 1) // 2,
                multiplier * (d['g1'] + d['g2'] + 1) // 2,
                multiplier * (d['b1'] + d['b2'] + 1) // 2,
            )
        return self._average

    def split(self) -> tuple[_VBox, ...]:
        count = self.count()
        if count == 0:
            return ()
        if count == 1:
            return (self.clone(),)

        d = self.dimension
        widths = {
            'r': d['r2'] - d['r1'] + 1,
            'g': d['g2'] - d['g1'] + 1,
            'b': d['b2'] - d['b1'] + 1,
        }
        # JavaScript's Math.max branch order resolves ties as red, green, blue.
        channel = max(widths, key=lambda name: (widths[name], -'rgb'.index(name)))
        lower = d[f'{channel}1']
        upper = d[f'{channel}2']
        cumulative = [0] * (upper + 1)
        total = 0

        for value in range(lower, upper + 1):
            subtotal = self._slice_count(channel, value)
            total += subtotal
            cumulative[value] = total

        split_point = next(
            value for value in range(lower, upper + 1) if cumulative[value] > total / 2
        )
        reverse = [total - value for value in cumulative]
        left_width = split_point - lower
        right_width = upper - split_point

        if left_width <= right_width:
            cut = min(upper - 1, int(split_point + right_width / 2))
            cut = max(0, cut)
        else:
            cut = max(lower, int(split_point - 1 - left_width / 2))
            cut = min(upper, cut)

        while cut <= upper and not cumulative[cut]:
            cut += 1
        if cut > upper:
            return (self.clone(),)

        remaining = reverse[cut]
        while cut > lower and not remaining and cumulative[cut - 1]:
            cut -= 1
            remaining = reverse[cut]

        first = self.clone()
        second = self.clone()
        first.dimension[f'{channel}2'] = cut
        second.dimension[f'{channel}1'] = cut + 1
        return first, second

    def _slice_count(self, channel: str, value: int) -> int:
        d = self.dimension
        values = self.histogram.values
        index = self.histogram.index
        ranges = {
            'r': range(d['r1'], d['r2'] + 1),
            'g': range(d['g1'], d['g2'] + 1),
            'b': range(d['b1'], d['b2'] + 1),
        }
        ranges[channel] = range(value, value + 1)
        return sum(
            values[index(red, green, blue)]
            for red in ranges['r']
            for green in ranges['g']
            for blue in ranges['b']
        )


class _PriorityQueue:
    def __init__(self, score: Callable[[_VBox], int]) -> None:
        self.items: list[_VBox] = []
        self.score = score

    def push(self, item: _VBox) -> None:
        self.items.append(item)

    def pop(self) -> _VBox | None:
        if not self.items:
            return None
        self.items.sort(key=self.score)
        return self.items.pop()

    def __len__(self) -> int:
        return len(self.items)


def _to_hex(color: str | RGB) -> str:
    if isinstance(color, tuple):
        red, green, blue = color
        return f'{red:02x}{green:02x}{blue:02x}'
    return color.lstrip('#').lower()


def _hex_to_rgb(color: str) -> RGB:
    value = color.lstrip('#').lower()
    if len(value) == 3:
        value = ''.join(character * 2 for character in value)
    if len(value) != 6:
        raise ValueError(f'Invalid hex color: {color}')
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _default_filter(red: int, green: int, blue: int, alpha: int) -> bool:
    """Match node-vibrant's default transparent and near-white pixel filter."""
    return alpha >= 125 and not (red > 250 and green > 250 and blue > 250)


def _split_boxes(queue: _PriorityQueue, target: float) -> None:
    last_size = len(queue)
    while len(queue) < target:
        vbox = queue.pop()
        if vbox is None or vbox.count() == 0:
            break

        boxes = vbox.split()
        if not boxes:
            break
        queue.push(boxes[0])
        if len(boxes) > 1 and boxes[1].count() > 0:
            queue.push(boxes[1])

        if len(queue) == last_size:
            break
        last_size = len(queue)


def quantize(pixels: Iterable[RGBA], color_count: int = 64) -> list[Swatch]:
    """Quantize RGBA pixels using node-vibrant's MMCQ implementation."""
    if color_count < 2 or color_count > 256:
        raise ValueError('color_count must be between 2 and 256')

    histogram = _Histogram(pixels)
    if histogram.color_count == 0:
        return []

    queue = _PriorityQueue(lambda box: box.count())
    queue.push(_VBox.build(histogram))
    _split_boxes(queue, _FRACTION_BY_POPULATION * color_count)

    volume_queue = _PriorityQueue(lambda box: box.count() * box.volume())
    volume_queue.items = queue.items
    # Preserve the current node-vibrant v4 MMCQ target calculation.
    _split_boxes(volume_queue, color_count - len(volume_queue))

    swatches: list[Swatch] = []
    while len(volume_queue):
        box = volume_queue.pop()
        if box is not None:
            swatches.append(Swatch(box.average(), box.count()))
    return swatches


def _comparison_value(
    saturation: float,
    target_saturation: float,
    luma: float,
    target_luma: float,
    population: int,
    max_population: int,
    options: _GeneratorOptions,
) -> float:
    values = (
        (1 - abs(saturation - target_saturation), options.weight_saturation),
        (1 - abs(luma - target_luma), options.weight_luma),
        (population / max_population, options.weight_population),
    )
    included = [(value, weight) for value, weight in values if value and weight]
    return sum(value * weight for value, weight in included) / sum(
        weight for _, weight in included
    )


def _find_variation(
    selected: Sequence[Swatch | None],
    swatches: Sequence[Swatch],
    max_population: int,
    target_luma: float,
    min_luma: float,
    max_luma: float,
    target_saturation: float,
    min_saturation: float,
    max_saturation: float,
    options: _GeneratorOptions,
) -> Swatch | None:
    best: Swatch | None = None
    best_value = 0.0
    for swatch in swatches:
        _, saturation, luma = swatch.hsl
        if (
            min_saturation <= saturation <= max_saturation
            and min_luma <= luma <= max_luma
            and all(swatch is not item for item in selected)
        ):
            value = _comparison_value(
                saturation,
                target_saturation,
                luma,
                target_luma,
                swatch.population,
                max_population,
                options,
            )
            if best is None or value > best_value:
                best = swatch
                best_value = value
    return best


def _synthetic_swatch(source: Swatch, lightness: float) -> Swatch:
    hue, saturation, _ = source.hsl
    red, green, blue = colorsys.hls_to_rgb(hue, lightness, saturation)
    return Swatch(
        (int(red * 255), int(green * 255), int(blue * 255)),
        population=0,
    )


def generate_palette(swatches: Sequence[Swatch]) -> VibrantPalette:
    """Classify MMCQ swatches with node-vibrant's default generator."""
    if not swatches:
        return VibrantPalette()

    options = _GeneratorOptions()
    max_population = max(swatch.population for swatch in swatches)
    selected: list[Swatch | None] = []

    def find(
        target_luma: float,
        min_luma: float,
        max_luma: float,
        target_saturation: float,
        min_saturation: float,
        max_saturation: float,
    ) -> Swatch | None:
        swatch = _find_variation(
            selected,
            swatches,
            max_population,
            target_luma,
            min_luma,
            max_luma,
            target_saturation,
            min_saturation,
            max_saturation,
            options,
        )
        selected.append(swatch)
        return swatch

    vibrant = find(
        options.target_normal_luma,
        options.min_normal_luma,
        options.max_normal_luma,
        options.target_vibrant_saturation,
        options.min_vibrant_saturation,
        1,
    )
    light_vibrant = find(
        options.target_light_luma,
        options.min_light_luma,
        1,
        options.target_vibrant_saturation,
        options.min_vibrant_saturation,
        1,
    )
    dark_vibrant = find(
        options.target_dark_luma,
        0,
        options.max_dark_luma,
        options.target_vibrant_saturation,
        options.min_vibrant_saturation,
        1,
    )
    muted = find(
        options.target_normal_luma,
        options.min_normal_luma,
        options.max_normal_luma,
        options.target_muted_saturation,
        0,
        options.max_muted_saturation,
    )
    light_muted = find(
        options.target_light_luma,
        options.min_light_luma,
        1,
        options.target_muted_saturation,
        0,
        options.max_muted_saturation,
    )
    dark_muted = find(
        options.target_dark_luma,
        0,
        options.max_dark_luma,
        options.target_muted_saturation,
        0,
        options.max_muted_saturation,
    )

    if vibrant is None and dark_vibrant is None and light_vibrant is None:
        if dark_muted is not None:
            dark_vibrant = _synthetic_swatch(dark_muted, options.target_dark_luma)
        if light_muted is not None:
            # This intentionally follows node-vibrant v4's fallback behavior.
            dark_vibrant = _synthetic_swatch(light_muted, options.target_dark_luma)

    if vibrant is None:
        source = dark_vibrant or light_vibrant
        if source is not None:
            vibrant = _synthetic_swatch(source, options.target_normal_luma)
    if dark_vibrant is None and vibrant is not None:
        dark_vibrant = _synthetic_swatch(vibrant, options.target_dark_luma)
    if light_vibrant is None and vibrant is not None:
        light_vibrant = _synthetic_swatch(vibrant, options.target_light_luma)
    if muted is None and vibrant is not None:
        muted = _synthetic_swatch(vibrant, options.target_muted_saturation)
    if dark_muted is None and dark_vibrant is not None:
        dark_muted = _synthetic_swatch(dark_vibrant, options.target_muted_saturation)
    if light_muted is None and light_vibrant is not None:
        light_muted = _synthetic_swatch(light_vibrant, options.target_muted_saturation)

    return VibrantPalette(
        vibrant=vibrant,
        dark_vibrant=dark_vibrant,
        light_vibrant=light_vibrant,
        muted=muted,
        dark_muted=dark_muted,
        light_muted=light_muted,
    )


def _load_pixels(
    path: str | Path, quality: int = 5
) -> tuple[list[RGBA], tuple[int, int]]:
    if quality < 1:
        raise ValueError('quality must be at least 1')

    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGBA')
        if quality > 1:
            width = max(1, image.width // quality)
            height = max(1, image.height // quality)
            image = image.resize((width, height), Image.Resampling.BILINEAR)
        return list(image.getdata()), image.size


def _extract_vibrant(
    path: str | Path, color_count: int = 64, quality: int = 5
) -> tuple[VibrantPalette, list[Swatch], tuple[int, int]]:
    pixels, size = _load_pixels(path, quality)
    swatches = quantize(pixels, color_count)
    return generate_palette(swatches), swatches, size


def extract_palette(path: str, color_count: int = 10) -> list[RGB]:
    """Extract raw MMCQ colors for palette debugging."""
    _, swatches, _ = _extract_vibrant(path, color_count=color_count)
    return [swatch.rgb for swatch in swatches]


def debug_palette(
    hex_colors: list[str] | None = None,
    palette: list[RGB] | None = None,
) -> None:
    """Print one or both color palettes in the terminal, with labels."""
    if hex_colors is None and palette is None:
        raise ValueError('You must pass either `hex_colors` or `palette`.')

    rows: list[tuple[str, list[str]]] = []
    if hex_colors:
        rows.append(('final colors', [_to_hex(color) for color in hex_colors]))
    if palette:
        rows.append(('quantized colors', [_to_hex(color) for color in palette]))
    if not rows:
        raise ValueError('At least one non-empty palette must be provided')

    console = Console()
    console.print('[bold]Palette debug[/bold]')
    for label, colors in rows:
        swatches_and_values = Text()
        for color in colors:
            try:
                red, green, blue = _hex_to_rgb(color)
                swatches_and_values.append(
                    '  ', style=Style(bgcolor=Color.from_rgb(red, green, blue))
                )
            except (TypeError, ValueError):
                pass
            swatches_and_values.append(f' #{color} ', style='dim')
        console.print(f'[bold cyan]{label:17}[/bold cyan]', swatches_and_values)


async def get_color_palette(path: str) -> list[str]:
    """Return node-vibrant-style palette colors for an image.

    The first color is the primary ``Vibrant`` swatch consumed by BeatBoard's
    hardware path. Remaining colors follow the dark-vibrant, light-vibrant,
    muted, dark-muted, and light-muted roles.
    """
    globs = Globs()
    start_time = time.perf_counter()
    palette, raw_swatches, size = _extract_vibrant(path)
    hex_colors = [swatch.hex for swatch in palette.swatches()]

    if globs.debug.get('perf') or globs.debug.get('all'):
        total_ms = (time.perf_counter() - start_time) * 1000
        print(
            f'[cyan]perf[/cyan] [dim]·[/dim] palette '
            f'[cyan]{total_ms:.0f}ms[/cyan] [dim]·[/dim] '
            f'{len(raw_swatches)}→{len(hex_colors)} colors [dim]·[/dim] '
            f'{size[0]}×{size[1]}'
        )

    if globs.debug.get('palette') or globs.debug.get('all'):
        debug_palette(hex_colors, [swatch.rgb for swatch in raw_swatches])

    return hex_colors
