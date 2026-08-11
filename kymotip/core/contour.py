"""輪郭抽出(SAM2マスク由来 / ImageJ Outline画像由来の2モード)。

検証事項3(DESIGN.md参照)の結論により、SAM2マスクからの輪郭抽出は
`skimage.measure.find_contours` を採用する(全フレームでresort()不要・
脱落0%・隣接点間距離が常に1.00pxと安定していたため)。

一方、ImageJの `Process > Binary > Outline` 等で生成された、順序を持たない
1px輪郭画像を読み込むレガシー互換モードも用意し、その場合のみ resort() で
並べ替える。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from .trajectory import resort


def extract_contour_ordered(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """SAM2などの塗りつぶしマスクから、順序付きの輪郭点列(x, y)を抽出する。

    find_contoursの出力は輪郭を一周する順に並んでいるため resort() は不要。
    """
    from skimage import measure

    contours = measure.find_contours(mask.astype(np.uint8), level=0.5)
    if not contours:
        raise ValueError("mask contains no contour (empty mask?)")
    largest = max(contours, key=len)
    y, x = largest[:, 0], largest[:, 1]
    return x, y


def extract_contour_from_outline_image(
    path: str | Path, resort_d: float = 3
) -> tuple[np.ndarray, np.ndarray]:
    """ImageJ Outline等の、順序を持たない1px輪郭画像から輪郭点列を抽出し、
    resort()で並べ替える(python_trajectory.ipynb の outline() 相当)。
    """
    from PIL import Image

    img = np.array(Image.open(path))
    y_coords, x_coords = np.where(img != 0)
    return resort(x_coords, y_coords, resort_d)
