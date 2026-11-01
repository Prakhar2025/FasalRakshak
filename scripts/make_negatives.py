"""Generate the fixed negative set for refusal evaluation.

Thirty deterministic, clearly non-leaf images (solid fills, gradients,
checkerboards, text-like stripes) rendered with Pillow. The generator is
versioned in the repository so the negative set is reproducible forever;
the images themselves stay local under data/negatives/.
"""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw

COUNT = 30
SIZE = 384
SEED = 20261104


def solid(rng: random.Random) -> Image.Image:
    color = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    return Image.new("RGB", (SIZE, SIZE), color)


def gradient(rng: random.Random) -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE))
    start = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    end = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
    for y in range(SIZE):
        for_kind = y / SIZE
        row = tuple(int(a + (b - a) * for_kind) for a, b in zip(start, end))
        ImageDraw.Draw(image).line([(0, y), (SIZE, y)], fill=row)
    return image


def checkerboard(rng: random.Random) -> Image.Image:
    cell = rng.choice([16, 24, 32])
    image = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for yy in range(0, SIZE, cell):
        for xx in range(0, SIZE, cell):
            shade = (xx // cell + yy // cell) % 2
            draw.rectangle(
                [xx, yy, xx + cell, yy + cell],
                fill=(shade * 40 + 20, shade * 40 + 30, shade * 40 + 25),
            )
    return image


def stripes(rng: random.Random) -> Image.Image:
    image = Image.new("RGB", (SIZE, SIZE), (250, 250, 250))
    draw = ImageDraw.Draw(image)
    for i in range(0, SIZE, rng.choice([8, 12, 18])):
        draw.line([(0, i), (SIZE, i)], fill=(60, 60, 60), width=3)
    return image


GENERATORS = [solid, gradient, checkerboard, stripes]


def main() -> None:
    out = Path("data/negatives")
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    for index in range(COUNT):
        image = GENERATORS[index % len(GENERATORS)](rng)
        image.save(out / f"neg_{index:03d}.png")
    print(f"done: {COUNT} negatives under {out}")


if __name__ == "__main__":
    main()
