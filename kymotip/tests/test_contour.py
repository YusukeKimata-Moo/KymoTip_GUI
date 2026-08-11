import numpy as np
from PIL import Image

from kymotip.core.contour import extract_contour_from_outline_image, extract_contour_ordered


def _disk_mask(radius=40, size=120):
    yy, xx = np.mgrid[0:size, 0:size]
    cy = cx = size // 2
    return ((yy - cy) ** 2 + (xx - cx) ** 2) <= radius**2


def test_extract_contour_ordered_from_disk_mask():
    mask = _disk_mask()
    x, y = extract_contour_ordered(mask)

    assert len(x) == len(y)
    assert len(x) > 100
    # 隣接点間の距離が常に小さい(輪郭が順序通りに並んでいる)ことを確認
    dists = np.hypot(np.diff(x), np.diff(y))
    assert dists.max() < 2.0


def test_extract_contour_from_outline_image(tmp_path):
    mask = _disk_mask()
    ys, xs = np.where(mask)
    from skimage import measure

    contour = max(measure.find_contours(mask.astype(np.uint8), level=0.5), key=len)
    outline = np.zeros(mask.shape, dtype=np.uint8)
    ry = np.round(contour[:, 0]).astype(int)
    rx = np.round(contour[:, 1]).astype(int)
    outline[ry, rx] = 255

    path = tmp_path / "outline.png"
    Image.fromarray(outline).save(path)

    x, y = extract_contour_from_outline_image(path, resort_d=3)

    assert len(x) > 50
    dists = np.hypot(np.diff(x), np.diff(y))
    assert dists.max() < 3
