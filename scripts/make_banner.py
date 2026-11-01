"""Render the 1200x675 banner: brand block left, real app screenshot right."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1200, 675
GREEN_TOP = (23, 130, 74)
GREEN_DEEP = (7, 42, 25)
FONTS = Path("C:/Windows/Fonts")


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size)


def rounded(image: Image.Image, radius: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, image.size[0], image.size[1]], radius=radius, fill=255)
    image.putalpha(mask)
    return image


def main() -> None:
    base = Image.new("RGB", (WIDTH, HEIGHT), GREEN_DEEP)
    draw = ImageDraw.Draw(base)
    for y in range(HEIGHT):
        blend = y / HEIGHT
        draw.line([(0, y), (WIDTH, y)], fill=tuple(int(a + (b - a) * blend) for a, b in zip(GREEN_TOP, GREEN_DEEP)))

    # right side: the real app screenshot, rounded, with a soft shadow plate
    shot = Image.open("C:/Users/prakh/brag-output/fasalrakshak/assets/shots/landing.png").convert("RGB")
    shot_w = 640
    shot_h = int(shot.height * shot_w / shot.width)
    shot = shot.resize((shot_w, shot_h))
    plate = Image.new("RGBA", (shot_w + 40, shot_h + 40), (0, 0, 0, 0))
    shadow = ImageDraw.Draw(plate)
    shadow.rounded_rectangle([18, 26, shot_w + 26, shot_h + 34], radius=24, fill=(0, 0, 0, 110))
    plate.paste(shot, (14, 12))
    plate = rounded(plate, 22)
    base.paste(plate, (530, (HEIGHT - plate.height) // 2), plate)

    # left: brand block
    draw.rounded_rectangle([64, 64, 136, 136], radius=22, fill=(255, 255, 255, 30))
    draw.polygon([(122, 84), (94, 128), (82, 118), (112, 86)], fill=(255, 255, 255))

    draw.text((64, 176), "FasalRakshak", font=font("segoeuib.ttf", 74), fill=(255, 255, 255))
    draw.text((68, 268), "the crop protector", font=font("segoeuii.ttf", 29), fill=(210, 234, 219))
    draw.text((64, 336), "A crop doctor in every", font=font("segoeuil.ttf", 33), fill=(255, 255, 255))
    draw.text((64, 380), "farmer's pocket.", font=font("segoeuil.ttf", 33), fill=(255, 255, 255))

    draw.line([(64, 470), (470, 470)], fill=(255, 255, 255, 70), width=2)
    for index, line in enumerate([
        "Voice-first, 10 Indian languages",
        "Deterministic safety gate: code decides",
        "Every advice cites its official source",
        "Live on AWS, 500-image published benchmark",
    ]):
        draw.text((64, 492 + index * 36), "+  " + line, font=font("segoeui.ttf", 21), fill=(214, 234, 222))

    draw.text((64, 628), "Strands Agents SDK · Amazon Bedrock · MIT", font=font("segoeuisl.ttf", 18), fill=(180, 210, 190))

    out = Path("docs/assets/banner.png")
    base.save(out)
    print(f"banner v2 written: {out}")


if __name__ == "__main__":
    main()
