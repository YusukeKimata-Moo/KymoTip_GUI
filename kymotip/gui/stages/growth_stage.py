"""Stage 7: Cell elongation (growth) plotting panel.

Input directory = centerline data (05_centerline output), output directory =
growth plots (PNG) and a CSV summary.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from ...core.growth import (
    compute_cell_lengths,
    compute_growth_rate,
    plot_cell_length,
    plot_growth_rate,
    plot_overlay,
    save_growth_csv,
    smooth_series_loess,
)
from .base import StageWidgetBase


class GrowthStage(StageWidgetBase):
    stage_title = "Growth"
    plugin_order = 7

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "05_centerline"))
        self.output_dir_picker.set_path(str(base_dir / "07_growth"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.fname_edit = QLineEdit()
        form_layout.addRow("File name prefix (centerline)", self.fname_edit)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

        self.add_auto_detect_button(form_layout, self.fname_edit, self.num_frames_spin)

        self.pixel_per_micron_spin = QDoubleSpinBox()
        self.pixel_per_micron_spin.setRange(0.001, 1000)
        self.pixel_per_micron_spin.setValue(1.0)
        form_layout.addRow("Pixels per micron", self.pixel_per_micron_spin)

        self.time_interval_spin = QDoubleSpinBox()
        self.time_interval_spin.setRange(0.001, 100000)
        self.time_interval_spin.setDecimals(3)
        self.time_interval_spin.setValue(1.0)
        self.time_interval_unit_combo = QComboBox()
        self.time_interval_unit_combo.addItems(["min", "sec"])
        interval_row = QWidget()
        interval_layout = QHBoxLayout(interval_row)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.addWidget(self.time_interval_spin)
        interval_layout.addWidget(self.time_interval_unit_combo)
        form_layout.addRow("Time interval (required)", interval_row)

        self.lowess_checkbox = QCheckBox("Apply LOWESS smoothing")
        self.lowess_checkbox.setChecked(True)
        form_layout.addRow(self.lowess_checkbox)

        self.lowess_degree_spin = QSpinBox()
        self.lowess_degree_spin.setRange(0, 5)
        self.lowess_degree_spin.setValue(2)
        form_layout.addRow("LOWESS degree", self.lowess_degree_spin)

        self.lowess_fraction_spin = QDoubleSpinBox()
        self.lowess_fraction_spin.setRange(0.01, 1.0)
        self.lowess_fraction_spin.setValue(0.3)
        form_layout.addRow("LOWESS fraction", self.lowess_fraction_spin)

        self.fig_width_spin = QDoubleSpinBox()
        self.fig_width_spin.setRange(1, 100)
        self.fig_width_spin.setValue(8.0)
        form_layout.addRow("Figure width (in)", self.fig_width_spin)

        self.fig_height_spin = QDoubleSpinBox()
        self.fig_height_spin.setRange(1, 100)
        self.fig_height_spin.setValue(5.0)
        form_layout.addRow("Figure height (in)", self.fig_height_spin)

        self.labsize_spin = QSpinBox()
        self.labsize_spin.setRange(4, 72)
        self.labsize_spin.setValue(12)
        form_layout.addRow("Label font size", self.labsize_spin)

        self.preview_plot_combo = QComboBox()
        self.preview_plot_combo.currentTextChanged.connect(self._render_preview)
        form_layout.addRow("Preview plot", self.preview_plot_combo)

    def _time_interval_sec(self) -> float:
        value = self.time_interval_spin.value()
        return value * 60 if self.time_interval_unit_combo.currentText() == "min" else value

    def build_task(self):
        fname = self.fname_edit.text().strip()
        if not fname:
            raise ValueError("File name prefix is required.")
        centerline_dir = self.input_dir_picker.path()
        if not centerline_dir:
            raise ValueError("Input directory is required.")
        output_dir = self.ensure_output_dir()

        num_frames = self.num_frames_spin.value()
        pixel_per_micron = self.pixel_per_micron_spin.value()
        time_interval_sec = self._time_interval_sec()
        apply_lowess = self.lowess_checkbox.isChecked()
        lowess_degree = self.lowess_degree_spin.value()
        lowess_fraction = self.lowess_fraction_spin.value()
        fig_size = (self.fig_width_spin.value(), self.fig_height_spin.value())
        labsize = self.labsize_spin.value()

        centerline_base_path = f"{centerline_dir}/{fname}"

        def task():
            cell_length_um = compute_cell_lengths(centerline_base_path, num_frames, pixel_per_micron)
            growth_rate = compute_growth_rate(cell_length_um, time_interval_sec)

            cell_length_smooth = None
            growth_rate_smooth = None
            if apply_lowess:
                cell_length_smooth = smooth_series_loess(cell_length_um, lowess_degree, lowess_fraction)
                growth_rate_smooth = smooth_series_loess(growth_rate, lowess_degree, lowess_fraction)

            frame_x = list(range(num_frames))
            time_min = [i * time_interval_sec / 60.0 for i in frame_x]
            xlabel = "Time (min)"

            csv_path = output_dir / f"{fname}_growth.csv"
            save_growth_csv(
                csv_path, frame_x, time_min, cell_length_um, cell_length_smooth,
                growth_rate, growth_rate_smooth,
            )

            length_path = plot_cell_length(
                time_min, cell_length_um, cell_length_smooth, xlabel,
                output_dir / f"{fname}_cell_length.png", fig_size=fig_size, labsize=labsize,
            )
            rate_path = plot_growth_rate(
                time_min, growth_rate, growth_rate_smooth, xlabel,
                output_dir / f"{fname}_growth_rate.png", fig_size=fig_size, labsize=labsize,
            )
            overlay_path = plot_overlay(
                time_min, cell_length_um, cell_length_smooth, growth_rate, growth_rate_smooth,
                xlabel, output_dir / f"{fname}_growth_overlay.png", fig_size=fig_size, labsize=labsize,
            )

            return {"Cell length": length_path, "Growth rate": rate_path, "Overlay": overlay_path}

        return task

    def on_task_finished(self, result) -> None:
        if not result:
            return
        self._preview_results = result
        combo = self.preview_plot_combo
        combo.blockSignals(True)
        previous = combo.currentText()
        combo.clear()
        combo.addItems(result.keys())
        select = previous if previous in result else next(iter(result))
        combo.setCurrentText(select)
        combo.blockSignals(False)
        self._render_preview(select)

    def _render_preview(self, plot_name: str) -> None:
        results = getattr(self, "_preview_results", None)
        if not results or plot_name not in results:
            return
        import matplotlib.image as mpimg

        image = mpimg.imread(results[plot_name])
        self.preview.ax.clear()
        self.preview.ax.imshow(image)
        self.preview.ax.set_axis_off()
        self.preview.redraw()
