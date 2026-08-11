"""Stage 4: Trajectory smoothing panel."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.io_utils import ensure_dir, frame_path, save_xy_plot
from ...core.trajectory import smooth_loess, smooth_moving_average
from .base import StageWidgetBase


class TrajectoryStage(StageWidgetBase):
    stage_title = "Trajectory Reordering"
    tab_label = "Trajectory"
    plugin_order = 4

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "03_contour"))
        self.output_dir_picker.set_path(str(base_dir / "04_trajectory"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.fname_edit = QLineEdit()
        form_layout.addRow("File name prefix", self.fname_edit)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

        self.add_auto_detect_button(form_layout, self.fname_edit, self.num_frames_spin)

        method_widget = QWidget()
        method_layout = QVBoxLayout(method_widget)
        method_layout.setContentsMargins(0, 0, 0, 0)
        self.loess_radio = QRadioButton("LOESS")
        self.moving_average_radio = QRadioButton("Cyclic moving average")
        self.loess_radio.setChecked(True)
        method_layout.addWidget(self.loess_radio)
        method_layout.addWidget(self.moving_average_radio)
        form_layout.addRow("Smoothing method", method_widget)

        self.loess_degree_spin = QSpinBox()
        self.loess_degree_spin.setRange(0, 5)
        self.loess_degree_spin.setValue(2)
        form_layout.addRow("LOESS degree", self.loess_degree_spin)

        self.loess_fraction_spin = QDoubleSpinBox()
        self.loess_fraction_spin.setRange(0.01, 1.0)
        self.loess_fraction_spin.setValue(0.3)
        form_layout.addRow("LOESS fraction", self.loess_fraction_spin)

        self.window_size_spin = QSpinBox()
        self.window_size_spin.setRange(3, 999)
        self.window_size_spin.setValue(5)
        form_layout.addRow("Moving average window size", self.window_size_spin)

        self.save_images_check = QCheckBox("Save preview images (PNG)")
        form_layout.addRow("", self.save_images_check)

    def build_task(self):
        fname = self.fname_edit.text().strip()
        if not fname:
            raise ValueError("File name prefix is required.")
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            raise ValueError("Input directory is required.")
        output_dir = self.ensure_output_dir()

        num_frames = self.num_frames_spin.value()
        use_loess = self.loess_radio.isChecked()
        degree = self.loess_degree_spin.value()
        fraction = self.loess_fraction_spin.value()
        window_size = self.window_size_spin.value()
        save_images = self.save_images_check.isChecked()
        image_size = self.get_reference_image_size(fname) if save_images else None
        images_dir = ensure_dir(output_dir / "images") if save_images else None

        def task():
            last_xy = None
            for frame in range(num_frames):
                in_path = frame_path(input_dir, fname, frame, "txt")
                data = np.loadtxt(in_path)
                x, y = data[:, 0], data[:, 1]

                if use_loess:
                    smoothed_x, smoothed_y = smooth_loess(x, y, degree, fraction)
                else:
                    smoothed_x, smoothed_y = smooth_moving_average(x, y, window_size)

                out_path = frame_path(output_dir, fname, frame, "txt")
                np.savetxt(out_path, np.column_stack([smoothed_x, smoothed_y]), fmt="%.6f")
                if save_images:
                    png_path = frame_path(images_dir, fname, frame, "png")
                    save_xy_plot(
                        png_path,
                        [
                            (x, y, {"linestyle": "None", "marker": "o", "markersize": 2, "color": "gray", "label": "Before smoothing"}),
                            (smoothed_x, smoothed_y, {"linestyle": "-", "color": "tab:red", "label": "After smoothing"}),
                        ],
                        image_size,
                    )
                last_xy = (smoothed_x, smoothed_y)
            return last_xy

        return task

    def on_task_finished(self, result) -> None:
        fname = self.fname_edit.text().strip()
        input_dir = self.input_dir_picker.path()
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

            in_path = frame_path(input_dir, fname, index, "txt")
            try:
                before_data = np.loadtxt(in_path)
                self.preview.ax.plot(
                    before_data[:, 0], before_data[:, 1], "o", markersize=2,
                    color="gray", label="Before smoothing",
                )
            except OSError:
                pass

            self.preview.ax.plot(data[:, 0], data[:, 1], "-", color="tab:red", label="After smoothing")
            self.preview.ax.set_aspect("equal")
            if image_size is not None:
                width, height = image_size
                self.preview.ax.set_xlim(0, width)
                self.preview.ax.set_ylim(height, 0)
            self.preview.ax.legend(loc="upper right", fontsize="small")
            self.preview.redraw()

        self.preview.set_frames(num_frames, render)
