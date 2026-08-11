"""Step 0: browse the raw input frames before running any processing stage.

Also hosts the project-wide settings (base directory / file name prefix) that
get propagated to every downstream stage via "Apply to All Stages".
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.io_utils import discover_frames, frame_path, normalize_for_display, read_image_any
from ..frame_browser import FrameBrowser
from ..settings import AppSettings
from .base import DirPicker


class InputPreviewStage(QWidget):
    stage_title = "Input Preview"

    def __init__(
        self,
        parent: QWidget | None = None,
        on_apply_project: Callable[[str, str], None] | None = None,
    ) -> None:
        super().__init__(parent)

        self._settings = AppSettings()
        self._on_apply_project = on_apply_project

        self.project_base_dir_picker = DirPicker("project base directory")
        self.project_base_dir_picker.set_path(self._settings.project_base_dir)

        self.fname_edit = QLineEdit(self._settings.project_fname)

        apply_button = QPushButton("Apply to All Stages")
        apply_button.clicked.connect(self._apply_project)

        self.input_dir_picker = DirPicker("input directory")
        load_button = QPushButton("Load frames")
        load_button.clicked.connect(self._load)

        self.status_label = QLabel("")

        form = QFormLayout()
        form.addRow("Project base directory", self.project_base_dir_picker)
        form.addRow("File name prefix", self.fname_edit)
        form.addRow(apply_button)
        form.addRow("Input directory", self.input_dir_picker)
        form.addRow(load_button)
        form.addRow(self.status_label)

        self.frame_browser = FrameBrowser()

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.frame_browser, stretch=1)

    def _apply_project(self) -> None:
        base_dir = self.project_base_dir_picker.path()
        fname = self.fname_edit.text().strip()

        self._settings.project_base_dir = base_dir
        self._settings.project_fname = fname

        if not base_dir or not fname:
            QMessageBox.warning(
                self, "Incomplete settings", "Project base directory and file name prefix are required."
            )
            return

        if self._on_apply_project is not None:
            self._on_apply_project(base_dir, fname)

    def _load(self) -> None:
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            self.status_label.setText("Input directory is required.")
            return

        result = discover_frames(input_dir)
        if result is None:
            self.status_label.setText(f"No '<name>_NNN.ext' frame files found in {input_dir}.")
            self.frame_browser.set_frames(0, lambda index: None)
            return

        fname, ext, num_frames = result
        self.status_label.setText(f"Detected: prefix='{fname}', ext='{ext}', frames={num_frames}")

        def render(index: int) -> None:
            path = frame_path(input_dir, fname, index, ext)
            try:
                image = read_image_any(path)
            except (FileNotFoundError, OSError):
                self.frame_browser.clear()
                return
            self.frame_browser.show_image(normalize_for_display(image))

        self.frame_browser.set_frames(num_frames, render)
