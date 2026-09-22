"""MMCQ quantization – Histogram, VBox, PriorityQueue, quantize."""

from __future__ import annotations

from typing import Callable, Iterable

from .constants import (
    _FRACTION_BY_POPULATION,
    _RSHIFT,
    _SIG_BITS,
    RGB,
    RGBA,
)
from .models import Swatch


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
            "r1": r1,
            "r2": r2,
            "g1": g1,
            "g2": g2,
            "b1": b1,
            "b2": b2,
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
            d["r1"], d["r2"], d["g1"], d["g2"], d["b1"], d["b2"], self.histogram
        )

    def volume(self) -> int:
        if self._volume is None:
            d = self.dimension
            self._volume = (
                (d["r2"] - d["r1"] + 1)
                * (d["g2"] - d["g1"] + 1)
                * (d["b2"] - d["b1"] + 1)
            )
        return self._volume

    def count(self) -> int:
        if self._count is None:
            d = self.dimension
            values = self.histogram.values
            index = self.histogram.index
            self._count = sum(
                values[index(red, green, blue)]
                for red in range(d["r1"], d["r2"] + 1)
                for green in range(d["g1"], d["g2"] + 1)
                for blue in range(d["b1"], d["b2"] + 1)
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

        for red in range(d["r1"], d["r2"] + 1):
            for green in range(d["g1"], d["g2"] + 1):
                for blue in range(d["b1"], d["b2"] + 1):
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
                multiplier * (d["r1"] + d["r2"] + 1) // 2,
                multiplier * (d["g1"] + d["g2"] + 1) // 2,
                multiplier * (d["b1"] + d["b2"] + 1) // 2,
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
            "r": d["r2"] - d["r1"] + 1,
            "g": d["g2"] - d["g1"] + 1,
            "b": d["b2"] - d["b1"] + 1,
        }
        # JavaScript's Math.max branch order resolves ties as red, green, blue.
        channel = max(widths, key=lambda name: (widths[name], -"rgb".index(name)))
        lower = d[f"{channel}1"]
        upper = d[f"{channel}2"]
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
        first.dimension[f"{channel}2"] = cut
        second.dimension[f"{channel}1"] = cut + 1
        return first, second

    def _slice_count(self, channel: str, value: int) -> int:
        d = self.dimension
        values = self.histogram.values
        index = self.histogram.index
        ranges = {
            "r": range(d["r1"], d["r2"] + 1),
            "g": range(d["g1"], d["g2"] + 1),
            "b": range(d["b1"], d["b2"] + 1),
        }
        ranges[channel] = range(value, value + 1)
        return sum(
            values[index(red, green, blue)]
            for red in ranges["r"]
            for green in ranges["g"]
            for blue in ranges["b"]
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
        raise ValueError("color_count must be between 2 and 256")

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
