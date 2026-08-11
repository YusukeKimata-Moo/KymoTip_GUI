import numpy as np

from kymotip.core.centerline import compute_centerline, save_centerline_data
from kymotip.core.contour import extract_contour_ordered


def _elongated_mask(h=140, w=400, ry=25, rx=170):
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h // 2, w // 2
    return (((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2) <= 1.0


def test_compute_centerline_on_elongated_shape(tmp_path):
    mask = _elongated_mask()
    x, y = extract_contour_ordered(mask)
    contour_yx = np.column_stack([y, x])

    centerline = compute_centerline(contour_yx, o=10, m1=10, m2=10, mm=65)

    assert centerline.ndim == 2
    assert centerline.shape[1] == 2
    assert len(centerline) > 10

    # Centerline should span most of the shape's long axis (width).
    span = centerline[:, 1].max() - centerline[:, 1].min()
    assert span > 200

    out_path = tmp_path / "centerline.txt"
    save_centerline_data(centerline, out_path)
    reloaded = np.loadtxt(out_path)
    assert reloaded.shape == centerline.shape
