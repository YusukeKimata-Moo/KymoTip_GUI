from pathlib import Path

import cv2
import numpy as np

from kymotip.core.centerline import compute_centerline, save_centerline_data
from kymotip.core.contour import extract_contour_ordered
from kymotip.core.kymograph import generate_kymograph, merge_kymograph, process_images


def _elongated_mask(h=140, w=400, ry=25, rx=170):
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h // 2, w // 2
    return (((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2) <= 1.0


def _make_frame_fixtures(tmp_path, num_frames=2):
    mask = _elongated_mask()
    x, y = extract_contour_ordered(mask)
    contour_yx = np.column_stack([y, x])
    centerline = compute_centerline(contour_yx, o=10, m1=10, m2=10, mm=65)

    image_base = tmp_path / "image"
    mask_base = tmp_path / "mask"
    centerline_base = tmp_path / "centerline"
    brightness_base = tmp_path / "brightness"

    rng = np.random.default_rng(0)
    for i in range(num_frames):
        image = (rng.random(mask.shape) * 50 + mask.astype(np.uint8) * 150).astype(np.uint8)
        cv2.imwrite(f"{image_base}_{i:03d}.png", image)
        cv2.imwrite(f"{mask_base}_{i:03d}.png", (mask.astype(np.uint8) * 255))
        save_centerline_data(centerline, f"{centerline_base}_{i:03d}.txt")

    return image_base, mask_base, centerline_base, brightness_base


def test_process_images_and_generate_kymograph(tmp_path):
    image_base, mask_base, centerline_base, brightness_base = _make_frame_fixtures(tmp_path)

    process_images(
        str(image_base), str(mask_base), str(centerline_base), str(brightness_base),
        num_images=2, sample_length=20,
    )

    for i in range(2):
        brightness_path = f"{brightness_base}_{i:03d}.txt"
        data = np.loadtxt(brightness_path)
        assert data.shape[1] == 3

    kymo_path = generate_kymograph(
        fname="test",
        brightness_path=str(brightness_base),
        num_images=2,
        out_path=str(tmp_path),
        fig_size=(4, 3),
        line_width=2,
        labsize=8,
        pixel_per_micron=1.0,
    )

    assert Path(kymo_path).is_file()


def test_merge_kymograph_generates_file(tmp_path, monkeypatch):
    from matplotlib.axes import Axes

    imshow_state = {}
    original_imshow = Axes.imshow

    def capture_imshow_state(self, *args, **kwargs):
        image = original_imshow(self, *args, **kwargs)
        imshow_state["xlim"] = self.get_xlim()
        imshow_state["ylim"] = self.get_ylim()
        imshow_state["aspect"] = self.get_aspect()
        return image

    monkeypatch.setattr(Axes, "imshow", capture_imshow_state)
    brightness_ch1 = tmp_path / "brightness_ch1"
    brightness_ch2 = tmp_path / "brightness_ch2"
    for i in range(2):
        coordinates = np.column_stack(
            (
                np.arange(5, dtype=float),
                np.zeros(5),
                np.linspace(10 + i, 100 + i, 5),
            )
        )
        np.savetxt(f"{brightness_ch1}_{i:03d}.txt", coordinates)
        coordinates[:, 2] = np.linspace(100 + i, 10 + i, 5)
        np.savetxt(f"{brightness_ch2}_{i:03d}.txt", coordinates)

    kymo_path = merge_kymograph(
        brightness_path_1=str(brightness_ch1),
        brightness_path_2=str(brightness_ch2),
        num_images=2,
        out_path=str(tmp_path),
        fig_size=(4, 3),
        line_width=2,
        labsize=8,
        pixel_per_micron=1.0,
        color1="red",
        color2="cyan",
    )

    assert Path(kymo_path).is_file()
    # marginはline_width/figure幅から実測されるデータ駆動値であり固定ではない
    # (単一チャンネルのgenerate_kymographと同じロジック)。
    xlim = imshow_state["xlim"]
    assert xlim[0] < 0 < 1 < xlim[1]
    assert np.allclose(xlim[0], -(xlim[1] - 1), atol=1e-6)
    assert np.allclose(imshow_state["ylim"], (0, 14))
    assert imshow_state["aspect"] == "auto"
