from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont


HERE = Path(__file__).resolve().parent
ICON_PATH = HERE / "kymotip.png"
FONT_PATH = Path(r"C:\Windows\Fonts\segoeuib.ttf")
SIZE = 1024
DARK = (30, 31, 34)
WHITE = (234, 241, 255)
BLUE = (76, 141, 255)
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _extract_mark() -> Image.Image:
    icon = Image.open(ICON_PATH).convert("RGBA")
    pixels = np.asarray(icon).copy()
    background = np.array(DARK, dtype=np.int16)
    difference = np.max(np.abs(pixels[:, :, :3].astype(np.int16) - background), axis=2)
    symbol_alpha = np.clip((difference - 3) * 8, 0, 255).astype(np.uint8)
    pixels[:, :, 3] = np.minimum(symbol_alpha, pixels[:, :, 3])
    mark = Image.fromarray(pixels, "RGBA")
    bounds = mark.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("Core Trace symbol could not be extracted")
    return mark.crop(bounds)


def _place_mark(mark: Image.Image) -> Image.Image:
    mark_height = 900
    mark_width = round(mark.width * mark_height / mark.height)
    resized = mark.resize((mark_width, mark_height), Image.Resampling.LANCZOS)
    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    layer.alpha_composite(resized, ((SIZE - mark_width) // 2, (SIZE - mark_height) // 2))
    return layer


def _make_text_layer() -> tuple[Image.Image, Image.Image]:
    text_layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    text_mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(text_layer)
    mask_draw = ImageDraw.Draw(text_mask)
    font = ImageFont.truetype(str(FONT_PATH), 178)

    full_text = "KymoTip"
    text_box = draw.textbbox((0, 0), full_text, font=font)
    text_width = draw.textlength(full_text, font=font)
    text_height = text_box[3] - text_box[1]
    x = (SIZE - text_width) / 2
    y = 520 - text_height / 2 - text_box[1]

    draw.text((x, y), "Kymo", font=font, fill=WHITE)
    mask_draw.text((x, y), "Kymo", font=font, fill=255)
    x += draw.textlength("Kymo", font=font)
    draw.text((x, y), "Tip", font=font, fill=BLUE)
    mask_draw.text((x, y), "Tip", font=font, fill=255)
    return text_layer, text_mask


def _compose_shortcut_icon() -> Image.Image:
    mark_layer = _place_mark(_extract_mark())
    text_layer, text_mask = _make_text_layer()
    knockout = text_mask.filter(ImageFilter.MaxFilter(31))

    mark_pixels = np.asarray(mark_layer).copy()
    knockout_pixels = np.asarray(knockout, dtype=np.uint16)
    mark_pixels[:, :, 3] = (
        mark_pixels[:, :, 3].astype(np.uint16) * (255 - knockout_pixels) // 255
    ).astype(np.uint8)

    canvas = Image.new("RGBA", (SIZE, SIZE), (*DARK, 255))
    canvas.alpha_composite(Image.fromarray(mark_pixels, "RGBA"))
    canvas.alpha_composite(text_layer)
    return canvas


def main() -> None:
    shortcut_icon = _compose_shortcut_icon()
    shortcut_icon.save(HERE / "kymotip-shortcut.png", optimize=True)
    shortcut_icon.save(HERE / "kymotip-shortcut.ico", format="ICO", sizes=ICO_SIZES)


if __name__ == "__main__":
    main()
