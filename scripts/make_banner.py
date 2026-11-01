"""Render the 2400x1350 banner: brand block left, real app screenshot right.

The logo is the real favicon rasterized to docs/assets/logo-512.png (see the
session note: Pillow cannot draw the SVG leaf path, so it is rendered in a
browser once and pasted here). The screenshot is the current live-app capture
from the video asset pool, so the banner always matches the shipped UI.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

WIDTH, HEIGHT = 2400, 1350
GREEN_TOP = (23, 130, 74)
GREEN_DEEP = (7, 42, 25)
FONTS = Path("C:/Windows/Fonts")
SHOT = Path("C:/Users/prakh/brag-output/fasalrakshak/assets/shots/landing-hi.png")
LOGO = Path("docs/assets/logo-512.png")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def rounded(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.size[0], image.size[1]], radius=radius, fill=255)
    image.putalpha(mask)
    return image


def paste_with_shadow(base: Image.Image, image: Image.Image, position: tuple[int, int], radius: int) -> None:
    """Paste an RGBA image with a soft drop shadow behind it."""
    shadow_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    shadow_box = [
        position[0] + 18,
        position[1] + 30,
        position[0] + image.width + 18,
        position[1] + image.height + 30,
    ]
    ImageDraw.Draw(shadow_layer).rounded_rectangle(shadow_box, radius=radius, fill=(0, 0, 0, 130))
    shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(28))
    base.alpha_composite(shadow_layer)
    base.alpha_composite(image, position)


def main() -> None:
    base = Image.new("RGB", (WIDTH, HEIGHT), GREEN_DEEP)
    draw = ImageDraw.Draw(base)
    for y in range(HEIGHT):
        blend = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=tuple(int(a + (b - a) * blend) for a, b in zip(GREEN_TOP, GREEN_DEEP)))
    base = base.convert("RGBA")

    # right side: the real app screenshot, rounded, with a soft shadow
    shot = Image.open(SHOT).convert("RGBA")
    shot_w = 1150
    shot_h = int(shot.height * shot_w / shot.width)
    shot = shot.resize((shot_w, shot_h), Image.LANCZOS)
    plate = rounded(shot.copy(), 36)
    paste_with_shadow(base, plate, (1140, (HEIGHT - shot_h) // 2 - 40), 36)

    # left: the real favicon as the brand mark, then the brand block
    logo = Image.open(LOGO).convert("RGBA").resize((150, 150), Image.LANCZOS)
    logo = rounded(logo, 38)
    base.alpha_composite(logo, (128, 118))

    draw = ImageDraw.Draw(base)
    draw.text((128, 330), "FasalRakshak", font=font("segoeuib.ttf", 150), fill=(255, 255, 255))
    draw.text((136, 520), "the crop protector", font=font("segoeuii.ttf", 58), fill=(210, 234, 219))
    draw.text((128, 640), "A crop doctor in every", font=font("segoeuil.ttf", 66), fill=(255, 255, 255))
    draw.text((128, 724), "farmer's pocket.", font=font("segoeuil.ttf", 66), fill=(255, 255, 255))

    draw.line([(128, 912), (960, 912)], fill=(255, 255, 255, 70), width=3)
    for index, line in enumerate([
        "Voice-first, 10 Indian languages",
        "Deterministic safety gate: code decides",
        "Every advice cites its official source",
        "Live on AWS, 500-image published benchmark",
    ]):
        draw.text((128, 950 + index * 74), "+  " + line, font=font("segoeui.ttf", 42), fill=(214, 234, 222))

    draw.text((128, 1252), "Strands Agents SDK · Amazon Bedrock · MIT", font=font("segoeuisl.ttf", 34), fill=(180, 210, 190))

    out = Path("docs/assets/banner.png")
    base.convert("RGB").save(out)
    print(f"banner v3 written: {out} ({WIDTH}x{HEIGHT})")


if __name__ == "__main__":
    main()
