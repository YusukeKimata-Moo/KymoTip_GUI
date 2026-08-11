"""Plugin: generic object position & width detection via Gaussian fitting.

Ports the analysis logic of
https://github.com/blues0910/KymoTip/blob/main/2.%20nucleus(MT%20band)_detection/NucleusDetection.ipynb
onto KymoTip's own pipeline outputs (03_contour, 05_centerline) instead of the
notebook's own ad-hoc contour/centerline text files. The detected "object" is
not limited to a nucleus/MT band -- it is whatever localized signal produces a
single peak in the intensity profile along the cell's length (a nucleus, an
MT band, an aggregate, etc.).

For each frame:
  1. Walk the centerline and, at each segment, find the pair of contour points
     that are "most perpendicular" to that segment (get_contour_points below;
     same idea as the notebook's function of the same name).
  2. Sample the raw intensity image along the line between each such point
     pair and average it, producing an intensity profile along the cell's
     length (a proxy for cross-sectional signal).
  3. Fit a 1D Gaussian (with baseline) to the normalized profile to obtain the
     object's center position and width, matching the notebook's
     threshold-based mu estimate + curve_fit for amplitude/sigma/baseline.

Only use names exported from kymotip.plugin_api; never import
kymotip.core / kymotip.gui internal modules directly. See
.claude/skills/kymotip-plugin-dev/references/PLUGIN_SPEC.md for the full
plugin specification.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from kymotip.plugin_api import (
    DirPicker,
    StageWidgetBase,
    append_log,
    discover_frames,
    ensure_dir,
    frame_path,
    read_image_any,
)


def calculate_path_length(points: np.ndarray) -> tuple[list[float], float]:
    """Cumulative length along a path (mirrors the notebook's function of the
    same name)."""
    cumulative_lengths: list[float] = []
    total_length = 0.0
    for i in range(1, len(points)):
        total_length += float(np.linalg.norm(points[i, :] - points[i - 1, :]))
        cumulative_lengths.append(total_length)
    return cumulative_lengths, total_length


def get_contour_points(xy: np.ndarray, cxy: np.ndarray, dcxy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each centerline segment, find the pair of contour points on either
    side that are most perpendicular to it (mirrors the notebook's function of
    the same name, both xy and cxy in (x, y) column order to match KymoTip's
    03_contour/05_centerline file format)."""
    lb = xy - cxy[0, :]
    lt = xy - cxy[-1, :]
    ib = int(np.argmin(np.linalg.norm(lb, axis=1)))
    it = int(np.argmin(np.linalg.norm(lt, axis=1)))
    xy = np.roll(xy, -ib, axis=0)
    it_shifted = (it - ib) % len(xy)

    points = np.zeros(dcxy.shape)
    for i in range(1, len(cxy)):
        v = xy - cxy[i, :]
        dots = np.abs(v @ dcxy[i - 1, :])
        points[i - 1, 0] = np.argmin(dots[:it_shifted])
        points[i - 1, 1] = np.argmin(dots[it_shifted:]) + it_shifted
    return xy, points


def linear_interpolate(xy1: np.ndarray, xy2: np.ndarray, n: int) -> np.ndarray:
    """n points linearly interpolated between xy1 and xy2 (mirrors the
    notebook's f())."""
    t = np.linspace(0.0, 1.0, n)
    return xy1[None, :] + t[:, None] * (xy2 - xy1)[None, :]


class GaussianFitDetectionStage(StageWidgetBase):
    stage_title = "Object Detection (Gaussian fit)"
    tab_label = "Gaussian Fit"
    plugin_order = 5.5
    plugin_api_version = 1

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.image_fname_edit.fname_customized = False
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "01_registration"))
        self.contour_dir_picker.set_path(str(base_dir / "03_contour"))
        self.centerline_dir_picker.set_path(str(base_dir / "05_centerline"))
        self.output_dir_picker.set_path(str(base_dir / "gaussian_fit_detection"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.input_dir_picker.edit.setPlaceholderText(
            "Registered images (01_registration), any channel"
        )

        self.fname_edit = QLineEdit()
        self.fname_edit.textChanged.connect(self._update_image_fname)
        form_layout.addRow("File name prefix (contour/centerline channel)", self.fname_edit)

        self.image_fname_edit = QLineEdit()
        self.image_fname_edit.fname_customized = False
        self.image_fname_edit.textEdited.connect(
            lambda _text: setattr(self.image_fname_edit, "fname_customized", True)
        )
        form_layout.addRow("Image file name prefix (detection channel)", self.image_fname_edit)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

        auto_detect_button = QPushButton("Auto-detect image prefix/frames from input directory")
        auto_detect_button.clicked.connect(self._auto_detect_image)
        form_layout.addRow(auto_detect_button)

        self.contour_dir_picker = DirPicker("contour directory")
        form_layout.addRow("Contour directory (03_contour)", self.contour_dir_picker)

        self.centerline_dir_picker = DirPicker("centerline directory")
        form_layout.addRow("Centerline directory (05_centerline)", self.centerline_dir_picker)

        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.01, 1.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(0.7)
        form_layout.addRow("Detection threshold (0-1)", self.threshold_spin)

        self.scc_spin = QDoubleSpinBox()
        self.scc_spin.setRange(0.01, 100)
        self.scc_spin.setSingleStep(0.1)
        self.scc_spin.setValue(1.3)
        form_layout.addRow("Width scale (scc, x sigma)", self.scc_spin)

        self.pixel_size_spin = QDoubleSpinBox()
        self.pixel_size_spin.setRange(1e-6, 100000)
        self.pixel_size_spin.setDecimals(6)
        self.pixel_size_spin.setValue(1.0)
        form_layout.addRow("Pixel size (px/um, 1.0 = px units)", self.pixel_size_spin)

        self.num_slice_samples_spin = QSpinBox()
        self.num_slice_samples_spin.setRange(2, 10000)
        self.num_slice_samples_spin.setValue(100)
        form_layout.addRow("Samples per cross-section slice", self.num_slice_samples_spin)

        self.save_images_check = QCheckBox("Save preview images (PNG)")
        form_layout.addRow("", self.save_images_check)

    def _update_image_fname(self, fname: str) -> None:
        if not self.image_fname_edit.fname_customized:
            self.image_fname_edit.setText(fname)

    def _auto_detect_image(self) -> None:
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            self.log("Input directory is required for auto-detect.")
            return
        result = discover_frames(input_dir)
        if result is None:
            self.log(f"No '<name>_NNN.ext' frame files found in {input_dir}.")
            return
        prefix, ext, num_frames = result
        self.image_fname_edit.fname_customized = True
        self.image_fname_edit.setText(prefix)
        self.num_frames_spin.setValue(num_frames)
        self.log(f"Auto-detected: image prefix='{prefix}', ext='{ext}', frames={num_frames}")

    def build_task(self):
        fname = self.fname_edit.text().strip()
        if not fname:
            raise ValueError("File name prefix (contour/centerline channel) is required.")
        image_fname = self.image_fname_edit.text().strip()
        if not image_fname:
            raise ValueError("Image file name prefix (detection channel) is required.")
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            raise ValueError("Input directory (registered image) is required.")
        contour_dir = self.contour_dir_picker.path()
        if not contour_dir:
            raise ValueError("Contour directory is required.")
        centerline_dir = self.centerline_dir_picker.path()
        if not centerline_dir:
            raise ValueError("Centerline directory is required.")
        output_dir = self.ensure_output_dir()

        num_frames = self.num_frames_spin.value()
        threshold = self.threshold_spin.value()
        scc = self.scc_spin.value()
        # UI入力はpx/um(1umあたりのpixel数)。既存の長さ計算はum/px(1pxあたりの
        # um数)を座標に乗算する前提のため、ここで逆数に変換する。
        pixel_size = 1.0 / self.pixel_size_spin.value()
        num_slice_samples = self.num_slice_samples_spin.value()
        save_images = self.save_images_check.isChecked()
        image_size = self.get_reference_image_size(fname) if save_images else None
        images_dir = ensure_dir(output_dir / "images") if save_images else None

        self._log_path = output_dir / f"{image_fname}_gaussian_fit.tsv"
        columns = [
            "frame", "center_position", "width", "total_length",
            "amplitude", "sigma", "baseline",
        ]

        def task():
            from scipy.ndimage import map_coordinates
            from scipy.optimize import curve_fit

            results = []
            for frame in range(num_frames):
                image_matches = sorted(Path(input_dir).glob(f"{image_fname}_{frame:03d}.*"))
                if not image_matches:
                    raise FileNotFoundError(f"No image found for frame {frame} in {input_dir}")
                img = read_image_any(image_matches[0]).astype(np.float64)
                if img.ndim == 3:
                    img = img.mean(axis=2)

                contour_xy = np.loadtxt(frame_path(contour_dir, fname, frame, "txt"))
                centerline_xy = np.loadtxt(frame_path(centerline_dir, fname, frame, "txt"))

                sx_list, total_length = calculate_path_length(centerline_xy * pixel_size)
                sx = np.array(sx_list)

                dcxy = centerline_xy[1:, :] - centerline_xy[:-1, :]
                ordered_xy, points = get_contour_points(contour_xy, centerline_xy, dcxy)

                profile = np.empty(len(points))
                for ip in range(len(points)):
                    p1 = ordered_xy[int(points[ip, 0])]
                    p2 = ordered_xy[int(points[ip, 1])]
                    slice_xy = linear_interpolate(p1, p2, num_slice_samples)
                    sampled = map_coordinates(
                        img, [slice_xy[:, 1], slice_xy[:, 0]], order=1, mode="nearest"
                    )
                    profile[ip] = np.mean(sampled)

                max_profile = np.max(profile)
                if max_profile <= 0:
                    raise ValueError(f"Frame {frame}: intensity profile is all zero.")
                tmpf = profile / max_profile

                above_threshold = sx[tmpf >= threshold]
                mu = float(np.mean(above_threshold)) if above_threshold.size else float(sx[np.argmax(tmpf)])

                def gaussian_function(x, amp, sigma, b, _mu=mu):
                    return amp * np.exp(-(x - _mu) ** 2 / (2 * sigma ** 2)) + b

                amp0 = float(np.max(tmpf) - np.min(tmpf))
                sigma0 = max(total_length / 10.0, 1e-3)
                b0 = float(np.min(tmpf))
                popt, _ = curve_fit(gaussian_function, sx, tmpf, p0=[amp0, sigma0, b0], maxfev=10000)
                amp, sigma, baseline = popt
                width = 2 * scc * abs(sigma)
                fit_curve = gaussian_function(sx, *popt)

                append_log(self._log_path, columns, {
                    "frame": frame,
                    "center_position": mu,
                    "width": width,
                    "total_length": total_length,
                    "amplitude": amp,
                    "sigma": sigma,
                    "baseline": baseline,
                })

                if save_images:
                    self._save_preview_image(
                        images_dir, image_fname, frame, img, centerline_xy, sx, tmpf, fit_curve,
                        mu, scc, sigma, image_size,
                    )

                results.append({
                    "sx": sx, "tmpf": tmpf, "fit_curve": fit_curve,
                    "center_position": mu, "width": width,
                })
            return results

        return task

    def _save_preview_image(
        self, images_dir, image_fname, frame, img, centerline_xy, sx, tmpf, fit_curve,
        mu, scc, sigma, image_size,
    ) -> None:
        from matplotlib.figure import Figure

        fig = Figure(figsize=(9, 4))
        ax_img, ax_profile = fig.subplots(1, 2, gridspec_kw={"width_ratios": [3, 1]})

        half_width = scc * abs(sigma)
        is1 = int(np.argmin(np.abs(sx - (mu - half_width))))
        is2 = int(np.argmin(np.abs(sx - (mu + half_width))))
        ax_img.imshow(img, cmap="gray")
        ax_img.plot(
            centerline_xy[is1:is2 + 1, 0], centerline_xy[is1:is2 + 1, 1],
            color="magenta", linewidth=2,
        )
        if image_size is not None:
            width, height = image_size
            ax_img.set_xlim(0, width)
            ax_img.set_ylim(height, 0)
        ax_img.set_title(f"Frame {frame}")
        ax_img.axis("off")

        ax_profile.plot(tmpf, sx, color="g", linewidth=1)
        ax_profile.plot(fit_curve, sx, "-.", color="k", linewidth=1)
        ax_profile.set_xlim(0, 1.1)
        ax_profile.set_ylim(0, sx[-1] if len(sx) else 1)

        fig.tight_layout()
        fig.savefig(images_dir / f"{image_fname}_{frame:03d}.png", dpi=150)

    def on_task_finished(self, result) -> None:
        if not result:
            return

        def render(index: int) -> None:
            r = result[index]
            self.preview.ax.clear()
            self.preview.ax.plot(r["sx"], r["tmpf"], color="g", linewidth=1, label="Profile")
            self.preview.ax.plot(r["sx"], r["fit_curve"], "-.", color="k", linewidth=1, label="Gaussian fit")
            self.preview.ax.axvline(r["center_position"], color="magenta", linewidth=1, label="Center")
            self.preview.ax.set_xlabel("Position along centerline")
            self.preview.ax.set_ylabel("Normalized intensity")
            self.preview.ax.legend(loc="upper right", fontsize="small")
            self.preview.redraw()

        self.preview.set_frames(len(result), render)
        self.log(f"Saved: {self._log_path}")
