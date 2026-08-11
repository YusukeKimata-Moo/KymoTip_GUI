"""Stage 5: Centerline extraction panel."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QCheckBox, QFormLayout, QLineEdit, QSpinBox

from ...core.centerline import compute_centerline, save_centerline_data
from ...core.io_utils import ensure_dir, frame_path, save_xy_plot
from .base import StageWidgetBase


class CenterlineStage(StageWidgetBase):
    stage_title = "Centerline Extraction"
    tab_label = "Centerline"
    plugin_order = 5

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "04_trajectory"))
        self.output_dir_picker.set_path(str(base_dir / "05_centerline"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.fname_edit = QLineEdit()
        form_layout.addRow("File name prefix", self.fname_edit)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

        self.add_auto_detect_button(form_layout, self.fname_edit, self.num_frames_spin)

        self.o_spin = QSpinBox()
        self.o_spin.setRange(1, 1000)
        self.o_spin.setValue(10)
        form_layout.addRow("Extension length (o)", self.o_spin)

        self.m1_spin = QSpinBox()
        self.m1_spin.setRange(0, 1000)
        self.m1_spin.setValue(10)
        form_layout.addRow("Path trim start (m1)", self.m1_spin)

        self.m2_spin = QSpinBox()
        self.m2_spin.setRange(0, 1000)
        self.m2_spin.setValue(10)
        form_layout.addRow("Path trim end (m2)", self.m2_spin)

        self.mm_spin = QSpinBox()
        self.mm_spin.setRange(1, 1000)
        self.mm_spin.setValue(65)
        form_layout.addRow("Moving average window (mm)", self.mm_spin)

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
        o = self.o_spin.value()
        m1 = self.m1_spin.value()
        m2 = self.m2_spin.value()
        mm = self.mm_spin.value()
        save_images = self.save_images_check.isChecked()
        image_size = self.get_reference_image_size(fname) if save_images else None
        images_dir = ensure_dir(output_dir / "images") if save_images else None

        def task():
            last_centerline = None
            for frame in range(num_frames):
                in_path = frame_path(input_dir, fname, frame, "txt")
                contour = np.loadtxt(in_path)
                centerline = compute_centerline(contour, o=o, m1=m1, m2=m2, mm=mm)

                out_path = frame_path(output_dir, fname, frame, "txt")
                save_centerline_data(centerline, out_path)
                if save_images:
                    png_path = frame_path(images_dir, fname, frame, "png")
                    save_xy_plot(
                        png_path,
                        [
                            (contour[:, 0], contour[:, 1], {"linestyle": "-", "color": "lightgray", "linewidth": 1, "label": "Contour"}),
                            (centerline[:, 0], centerline[:, 1], {"linestyle": "-", "marker": "o", "markersize": 2, "color": "tab:red", "label": "Centerline"}),
                        ],
                        image_size,
                    )
                last_centerline = centerline
            return last_centerline

        return task

    def on_task_finished(self, result) -> None:
        fname = self.fname_edit.text().strip()
        input_dir = self.input_dir_picker.path()
        output_dir = self.ensure_output_dir()
        num_frames = self.num_frames_spin.value()
        image_size = self.get_reference_image_size(fname)

        def render(index: int) -> None:
            centerline_path = frame_path(output_dir, fname, index, "txt")
            try:
                centerline_data = np.loadtxt(centerline_path)
            except OSError:
                self.preview.clear()
                return
            self.preview.ax.clear()

            contour_path = frame_path(input_dir, fname, index, "txt")
            try:
                contour_data = np.loadtxt(contour_path)
                self.preview.ax.plot(
                    contour_data[:, 0], contour_data[:, 1], "-", color="lightgray", linewidth=1, label="Contour"
                )
            except OSError:
                pass

            self.preview.ax.plot(
                centerline_data[:, 0], centerline_data[:, 1], "-o", markersize=2, color="tab:red", label="Centerline"
            )
            self.preview.ax.set_aspect("equal")
            if image_size is not None:
                width, height = image_size
                self.preview.ax.set_xlim(0, width)
                self.preview.ax.set_ylim(height, 0)
            self.preview.ax.legend(loc="upper right", fontsize="small")
            self.preview.redraw()

        self.preview.set_frames(num_frames, render)
