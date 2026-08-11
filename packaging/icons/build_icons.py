from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


HERE = Path(__file__).resolve().parent
CONCEPTS_DIR = HERE / "concepts"
SOURCE_PATH = CONCEPTS_DIR / "kymotip-core-trace-source.png"
CANVAS_SIZE = 1024
DARK = (30, 31, 34)
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _rounded_mask(size: int, radius: int) -> Image.Image:
    scale = 4
    mask = Image.new("L", (size * scale, size * scale), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, size * scale - 1, size * scale - 1),
        radius=radius * scale,
        fill=255,
    )
    return mask.resize((size, size), Image.Resampling.LANCZOS)


def _prepare_master(source_path: Path) -> Image.Image:
    source = Image.open(source_path).convert("RGB")
    for corner in ((0, 0), (source.width - 1, 0), (0, source.height - 1), (source.width - 1, source.height - 1)):
        if min(source.getpixel(corner)) > 170:
            ImageDraw.floodfill(source, corner, DARK, thresh=90)

    source = source.resize((CANVAS_SIZE, CANVAS_SIZE), Image.Resampling.LANCZOS)
    pixels = np.asarray(source).copy()
    red = pixels[:, :, 0].astype(np.int16)
    green = pixels[:, :, 1].astype(np.int16)
    blue = pixels[:, :, 2].astype(np.int16)
    neutral_dark = (pixels.max(axis=2) < 105) & (blue - np.maximum(red, green) < 30)
    pixels[neutral_dark] = DARK

    master = Image.fromarray(pixels, "RGB").convert("RGBA")
    master.putalpha(_rounded_mask(CANVAS_SIZE, radius=210))
    return master


def main() -> None:
    master = _prepare_master(SOURCE_PATH)
    master.save(HERE / "kymotip.png", optimize=True)
    master.save(HERE / "kymotip.ico", format="ICO", sizes=ICO_SIZES)
    master.save(HERE / "kymotip.icns", format="ICNS")


if __name__ == "__main__":
    main()
