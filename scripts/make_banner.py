"""Render the 1200x675 project banner with Pillow.

Brand: deep-green gradient field, a drawn leaf mark, the wordmark in a
strong sans, the tagline, and the trust line. Saved to
docs/assets/banner.png and used at the top of the README and article.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 675
GREEN_TOP = (21, 122, 69)
GREEN_DEEP = (8, 48, 28)
ACCENT = (210, 234, 219)

FONT_DIR = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def main() -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), GREEN_DEEP)
    draw = ImageDraw.Draw(image)

    # vertical gradient
    for y in range(HEIGHT):
        blend = y / HEIGHT
        row = tuple(int(a + (b - a) * blend) for a, b in zip(GREEN_TOP, GREEN_DEEP))
        draw.line([(0, y), (WIDTH, y)], fill=row)

    # large translucent leaf silhouette on the right
    leaf = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    leaf_draw = ImageDraw.Draw(leaf)
    leaf_draw.polygon(
        [(760, 590), (880, 360), (1060, 240), (1150, 430), (1080, 620), (900, 660)],
        fill=(255, 255, 255, 14),
    )
    leaf_draw.line([(790, 600), (1090, 280)], fill=(255, 255, 255, 26), width=6)
    image = Image.alpha_composite(image.convert("RGBA"), leaf).convert("RGB")
    draw = ImageDraw.Draw(image)

    # leaf mark, top left
    draw.rounded_rectangle([70, 64, 142, 136], radius=22, fill=(255, 255, 255, 26), outline=None)
    draw.polygon(
        [(128, 84), (100, 128), (88, 118), (118, 86)], fill=(255, 255, 255)
    )
    draw.arc([96, 96, 132, 132], start=200, end=340, fill=ACCENT, width=4)

    # wordmark + subtitle
    title = font("segoeuib.ttf", 78)
    subtitle = font("segoeui.ttf", 34)
    body = font("segoeui.ttf", 24)
    small = font("segoeuisl.ttf", 20)

    draw.text((70, 180), "FasalRakshak", font=title, fill=(255, 255, 255))
    draw.text((74, 276), "the crop protector", font=font("segoeuii.ttf", 30), fill=ACCENT)
    draw.text(
        (70, 350),
        "A crop doctor in every farmer's pocket.",
        font=subtitle,
        fill=(255, 255, 255),
    )
    draw.text(
        (70, 402),
        "Photo of a sick leaf in, safe treatment plan spoken out. In 10 Indian languages.",
        font=body,
        fill=(214, 234, 222),
    )

    # divider + trust line
    draw.line([(70, 500), (820, 500)], fill=(255, 255, 255, 60), width=2)
    draw.text(
        (70, 528),
        "Built with the Strands Agents SDK on Amazon Bedrock",
        font=body,
        fill=(255, 255, 255),
    )
    draw.text(
        (70, 566),
        "Lambda + API Gateway + DynamoDB + Transcribe + Polly  |  models propose, code decides",
        font=small,
        fill=ACCENT,
    )
    draw.text(
        (70, 610),
        "500-image published benchmark  |  MIT  |  github.com/Prakhar2025/FasalRakshak",
        font=small,
        fill=(190, 216, 199),
    )

    out = Path("docs/assets/banner.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
    print(f"banner written: {out} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
