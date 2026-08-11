"""Stage 3: Contour extraction panel."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.contour import extract_contour_from_outline_image, extract_contour_ordered
from ...core.io_utils import ensure_dir, frame_path, save_xy_plot
from .base import StageWidgetBase

_MASK_RE = re.compile(r"^mask_(\d{3})_(.+)\.[A-Za-z0-9]+$")


class ContourStage(StageWidgetBase):
    stage_title = "Contour Extraction"
    tab_label = "Contour"
    plugin_order = 3

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "02_segmentation"))
        self.output_dir_picker.set_path(str(base_dir / "03_contour"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.fname_edit = QLineEdit()
        form_layout.addRow("File name prefix", self.fname_edit)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

        auto_detect_button = QPushButton("Auto-detect from input directory")
        auto_detect_button.clicked.connect(self._auto_detect)
        form_layout.addRow(auto_detect_button)

        mode_widget = QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self.mask_mode_radio = QRadioButton("Filled mask (skimage)")
        self.outline_mode_radio = QRadioButton("Ordered outline (ImageJ)")
        self.mask_mode_radio.setToolTip("From filled mask (skimage)")
        self.outline_mode_radio.setToolTip("From ordered outline image (ImageJ)")
        self.mask_mode_radio.setChecked(True)
        mode_layout.addWidget(self.mask_mode_radio)
        mode_layout.addWidget(self.outline_mode_radio)
        form_layout.addRow("Mode", mode_widget)

        self.resort_d_spin = QDoubleSpinBox()
        self.resort_d_spin.setRange(0.1, 1000)
        self.resort_d_spin.setValue(3)
        form_layout.addRow("Resort distance threshold (d)", self.resort_d_spin)

        self.object_id_edit = QLineEdit("obj0")
        form_layout.addRow("Tracked object ID (mask mode)", self.object_id_edit)

        self.save_images_check = QCheckBox("Save preview images (PNG)")
        form_layout.addRow("", self.save_images_check)

    def _auto_detect(self) -> None:
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            QMessageBox.warning(self, "Invalid input", "Input directory is required.")
            return

        if self.mask_mode_radio.isChecked():
            object_id = self.object_id_edit.text().strip()
            frame_indices: list[int] = []
            found_object_ids: set[str] = set()
            for entry in Path(input_dir).iterdir():
                if not entry.is_file():
                    continue
                match = _MASK_RE.match(entry.name)
                if not match:
                    continue
                frame_str, oid = match.groups()
                found_object_ids.add(oid)
                if not object_id or oid == object_id:
                    frame_indices.append(int(frame_str))

            if not frame_indices:
                QMessageBox.warning(
                    self,
                    "Not found",
                    f"No 'mask_NNN_<object_id>.ext' files found in {input_dir}"
                    + (f" for object '{object_id}'." if object_id else "."),
                )
                return

            if not object_id and found_object_ids:
                object_id = sorted(found_object_ids)[0]
                self.object_id_edit.setText(object_id)

            num_frames = max(frame_indices) + 1
            self.num_frames_spin.setValue(num_frames)
            self.log(f"Auto-detected: object_id='{object_id}', frames={num_frames}")
        else:
            from ...core.io_utils import discover_frames

            result = discover_frames(input_dir)
            if result is None:
                QMessageBox.warning(
                    self,
                    "Not found",
                    f"No '<name>_NNN.ext' frame files found in {input_dir}.",
                )
                return

            prefix, ext, num_frames = result
            self.detected_ext = ext
            self.fname_edit.setText(prefix)
            self.num_frames_spin.setValue(num_frames)
            self.log(f"Auto-detected: prefix='{prefix}', ext='{ext}', frames={num_frames}")

    def build_task(self):
        fname = self.fname_edit.text().strip()
        if not fname:
            raise ValueError("File name prefix is required.")
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            raise ValueError("Input directory is required.")
        output_dir = self.ensure_output_dir()

        num_frames = self.num_frames_spin.value()
        use_mask_mode = self.mask_mode_radio.isChecked()
        resort_d = self.resort_d_spin.value()
        object_id = self.object_id_edit.text().strip()
        if use_mask_mode and not object_id:
            raise ValueError("Tracked object ID is required in mask mode.")
        save_images = self.save_images_check.isChecked()
        image_size = self.get_reference_image_size(fname) if save_images else None
        images_dir = ensure_dir(output_dir / "images") if save_images else None

        def task():
            last_xy = None
            for frame in range(num_frames):
                if use_mask_mode:
                    from PIL import Image

                    matches = sorted(Path(input_dir).glob(f"mask_{frame:03d}_{object_id}.*"))
                    if not matches:
                        raise FileNotFoundError(
                            f"Mask not found for frame {frame}, object {object_id} in {input_dir}"
                        )
                    mask = np.array(Image.open(matches[0]))
                    x, y = extract_contour_ordered(mask)
                else:
                    image_path = frame_path(input_dir, fname, frame, "png")
                    x, y = extract_contour_from_outline_image(image_path, resort_d=resort_d)

                out_path = frame_path(output_dir, fname, frame, "txt")
                np.savetxt(out_path, np.column_stack([x, y]), fmt="%.6f")
                if save_images:
                    png_path = frame_path(images_dir, fname, frame, "png")
                    save_xy_plot(png_path, [(x, y, {"linestyle": "-", "marker": "o", "markersize": 2})], image_size)
                last_xy = (x, y)
            return last_xy

        return task

    def on_task_finished(self, result) -> None:
        fname = self.fname_edit.text().strip()
        output_dir = self.ensure_output_dir()
        num_frames = self.num_frames_spin.value()
        image_size = self.get_reference_image_size(fname)

        def render(index: int) -> None:
            path = frame_path(output_dir, fname, index, "txt")
            try:
                data = np.loadtxt(path)
            except OSError:
                self.preview.clear()
                return
            self.preview.ax.clear()
            self.preview.ax.plot(data[:, 0], data[:, 1], "-o", markersize=2)
            self.preview.ax.set_aspect("equal")
            if image_size is not None:
                width, height = image_size
                self.preview.ax.set_xlim(0, width)
                self.preview.ax.set_ylim(height, 0)
            self.preview.redraw()

        self.preview.set_frames(num_frames, render)
