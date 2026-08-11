"""Stage 6: Kymograph generation panel.

Input directory = original grayscale images, output directory = kymograph PNG
and intermediate brightness profiles. Mask and centerline directories are
selected separately since they come from earlier stages' own output folders.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.kymograph import (
    estimate_optimal_line_width,
    generate_kymograph,
    merge_kymograph,
    process_images,
)
from .base import DirPicker, StageWidgetBase


class KymographStage(StageWidgetBase):
    stage_title = "Kymograph"
    plugin_order = 6

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "01_registration"))
        self.mask_dir_picker.set_path(str(base_dir / "02_segmentation"))
        self.centerline_dir_picker.set_path(str(base_dir / "05_centerline"))
        self.output_dir_picker.set_path(str(base_dir / "06_kymograph"))
    # 元notebookの実測値(fig_size=(5,5), line_width=7.5, num_images=66)は、
    # 隙間ゼロの理論値(約2.97pt)の約2.5倍太かった。この重なりが点ごとの
    # 輝度ノイズによる継ぎ目を目立たなくしていたが、実際にGUIで試したところ
    # x2.5では太すぎたため、x1.4に調整。
    NOTEBOOK_STYLE_OVERLAP_FACTOR = 1.4

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.fname_edit = QLineEdit()
        self.fname_edit.textChanged.connect(self._update_extra_channel_fname)
        form_layout.addRow("File name prefix (Channel 1)", self.fname_edit)

        self.input_dir_picker.edit.textChanged.connect(self._update_extra_channel_dir)

        mode_widget = QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self.ch1_radio = QRadioButton("1 channel")
        self.ch2_radio = QRadioButton("2 channels")
        self.ch1_radio.setChecked(True)
        for radio in (self.ch1_radio, self.ch2_radio):
            radio.toggled.connect(self._update_channel_visibility)
            mode_layout.addWidget(radio)
        form_layout.addRow("Number of channels", mode_widget)

        self.ch2_group = self._build_extra_channel_group()
        form_layout.addRow(self.ch2_group)
        self.ch2_group.setVisible(False)

        color_presets = ["magenta", "green", "red", "cyan", "yellow", "orange"]
        self.ch1_color_combo = QComboBox()
        self.ch1_color_combo.addItems(color_presets)
        form_layout.addRow("Channel 1 color", self.ch1_color_combo)

        self.ch2_color_combo = QComboBox()
        self.ch2_color_combo.addItems(color_presets)
        self.ch2_color_combo.setCurrentText("green")
        form_layout.addRow("Channel 2 color", self.ch2_color_combo)

        self.adjust_color_range_checkbox = QCheckBox("Adjust color range to data max")
        self.adjust_color_range_checkbox.setChecked(True)
        form_layout.addRow("Color range", self.adjust_color_range_checkbox)

        self.preview_channel_combo = QComboBox()
        self.preview_channel_combo.currentTextChanged.connect(self._render_preview)
        form_layout.addRow("Preview channel", self.preview_channel_combo)

        self.mask_dir_picker = DirPicker("mask directory")
        form_layout.addRow("Mask directory", self.mask_dir_picker)

        self.object_id_edit = QLineEdit("obj0")
        form_layout.addRow("Tracked object ID", self.object_id_edit)

        self.centerline_dir_picker = DirPicker("centerline directory")
        form_layout.addRow("Centerline directory", self.centerline_dir_picker)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

        self.add_auto_detect_button(form_layout, self.fname_edit, self.num_frames_spin)

        self.sample_length_spin = QSpinBox()
        self.sample_length_spin.setRange(1, 1000)
        self.sample_length_spin.setValue(100)
        form_layout.addRow("Normal sample length (px)", self.sample_length_spin)

        self.fig_width_spin = QDoubleSpinBox()
        self.fig_width_spin.setRange(1, 100)
        self.fig_width_spin.setValue(8.0)
        form_layout.addRow("Figure width (in)", self.fig_width_spin)

        self.fig_height_spin = QDoubleSpinBox()
        self.fig_height_spin.setRange(1, 100)
        self.fig_height_spin.setValue(6.0)
        form_layout.addRow("Figure height (in)", self.fig_height_spin)

        self.labsize_spin = QSpinBox()
        self.labsize_spin.setRange(4, 72)
        self.labsize_spin.setValue(12)
        form_layout.addRow("Label font size", self.labsize_spin)

        self.line_width_spin = QDoubleSpinBox()
        self.line_width_spin.setRange(0.1, 50)
        self.line_width_spin.setValue(2.0)
        form_layout.addRow("Line width", self.line_width_spin)

        self.estimate_line_width_button = QPushButton("Estimate optimal line width")
        self.estimate_line_width_button.clicked.connect(self._on_estimate_line_width)
        form_layout.addRow("", self.estimate_line_width_button)

        self.pixel_per_micron_spin = QDoubleSpinBox()
        self.pixel_per_micron_spin.setRange(0.001, 1000)
        self.pixel_per_micron_spin.setValue(1.0)
        form_layout.addRow("Pixels per micron", self.pixel_per_micron_spin)

        self.time_interval_spin = QDoubleSpinBox()
        self.time_interval_spin.setRange(0, 100000)
        self.time_interval_spin.setDecimals(3)
        self.time_interval_spin.setValue(0.0)
        self.time_interval_spin.setSpecialValueText("Unset (frame index)")
        self.time_interval_unit_combo = QComboBox()
        self.time_interval_unit_combo.addItems(["min", "sec"])
        interval_row = QWidget()
        interval_layout = QHBoxLayout(interval_row)
        interval_layout.setContentsMargins(0, 0, 0, 0)
        interval_layout.addWidget(self.time_interval_spin)
        interval_layout.addWidget(self.time_interval_unit_combo)
        form_layout.addRow("Time interval", interval_row)

        self.time_axis_unit_combo = QComboBox()
        self.time_axis_unit_combo.addItems(["min", "sec"])
        form_layout.addRow("Time axis unit", self.time_axis_unit_combo)

    def _build_extra_channel_group(self) -> QGroupBox:
        group = QGroupBox("Channel 2")
        layout = QFormLayout(group)
        input_picker = DirPicker("Channel 2 input directory")
        fname_edit = QLineEdit()
        input_picker.dir_customized = False
        fname_edit.fname_customized = False

        input_picker.pathEdited.connect(lambda _text: setattr(input_picker, "dir_customized", True))
        fname_edit.textEdited.connect(lambda _text: setattr(fname_edit, "fname_customized", True))
        layout.addRow("Input directory", input_picker)
        layout.addRow("File name prefix", fname_edit)
        group.input_dir_picker = input_picker
        group.fname_edit = fname_edit
        return group

    def _update_extra_channel_fname(self, fname: str) -> None:
        if not self.ch2_group.fname_edit.fname_customized:
            self.ch2_group.fname_edit.setText(f"{fname}_ch2" if fname else "")

    def _update_extra_channel_dir(self, base_path: str) -> None:
        picker = self.ch2_group.input_dir_picker
        if picker.dir_customized:
            return
        base_path = base_path.strip()
        if not base_path:
            picker.set_path("")
            return
        path = Path(base_path)
        picker.set_path(str(path.parent / f"{path.name}_ch2"))

    def _update_channel_visibility(self) -> None:
        self.ch2_group.setVisible(self.ch2_radio.isChecked())

    def _time_interval_sec(self) -> float | None:
        value = self.time_interval_spin.value()
        if not value:
            return None
        return value * 60 if self.time_interval_unit_combo.currentText() == "min" else value

    def _on_estimate_line_width(self) -> None:
        fig_size = (self.fig_width_spin.value(), self.fig_height_spin.value())
        gap_free_width = estimate_optimal_line_width(
            fig_size,
            self.num_frames_spin.value(),
            labsize=self.labsize_spin.value(),
            time_interval_sec=self._time_interval_sec(),
            axis_unit=self.time_axis_unit_combo.currentText(),
        )
        estimated = gap_free_width * self.NOTEBOOK_STYLE_OVERLAP_FACTOR
        estimated = max(self.line_width_spin.minimum(), min(self.line_width_spin.maximum(), estimated))
        self.line_width_spin.setValue(estimated)

    def build_task(self):
        fname = self.fname_edit.text().strip()
        if not fname:
            raise ValueError("File name prefix is required.")
        image_dir = self.input_dir_picker.path()
        mask_dir = self.mask_dir_picker.path()
        centerline_dir = self.centerline_dir_picker.path()
        object_id = self.object_id_edit.text().strip()
        if not (image_dir and mask_dir and centerline_dir and object_id):
            raise ValueError("Image, mask, centerline directories and object ID are all required.")
        output_dir = self.ensure_output_dir()

        use_two_channels = self.ch2_radio.isChecked()
        ch2_fname = self.ch2_group.fname_edit.text().strip()
        ch2_image_dir = self.ch2_group.input_dir_picker.path()
        if use_two_channels and not (ch2_fname and ch2_image_dir):
            raise ValueError("Channel 2: image directory and file name prefix are required.")

        num_frames = self.num_frames_spin.value()
        sample_length = self.sample_length_spin.value()
        line_width = self.line_width_spin.value()
        labsize = self.labsize_spin.value()
        pixel_per_micron = self.pixel_per_micron_spin.value()
        time_interval_sec = self._time_interval_sec()
        axis_unit = self.time_axis_unit_combo.currentText()
        color1 = self.ch1_color_combo.currentText()
        color2 = self.ch2_color_combo.currentText()
        adjust_color_range = self.adjust_color_range_checkbox.isChecked()

        image_base_path = f"{image_dir}/{fname}"
        centerline_base_path = f"{centerline_dir}/{fname}"
        brightness_base_path = f"{output_dir}/{fname}_brightness"
        ch2_image_base_path = f"{ch2_image_dir}/{ch2_fname}"
        ch2_brightness_base_path = f"{output_dir}/{ch2_fname}_brightness"

        def mask_path_fn(frame: int) -> str:
            return f"{mask_dir}/mask_{frame:03d}_{object_id}.png"

        def task():
            process_images(
                image_base_path,
                None,
                centerline_base_path,
                brightness_base_path,
                num_frames,
                sample_length=sample_length,
                mask_path_fn=mask_path_fn,
                image_ext=self.detected_ext,
            )
            kymo_path = generate_kymograph(
                fname,
                brightness_base_path,
                num_frames,
                str(output_dir),
                fig_size=(self.fig_width_spin.value(), self.fig_height_spin.value()),
                line_width=line_width,
                labsize=labsize,
                pixel_per_micron=pixel_per_micron,
                adjust_color_range=adjust_color_range,
                time_interval_sec=time_interval_sec,
                axis_unit=axis_unit,
            )
            if not use_two_channels:
                return {"Channel 1": kymo_path}

            # 中心線とマスクはチャネル間で共通なので、蛍光画像だけを切り替えて再サンプリングする。
            process_images(
                ch2_image_base_path,
                None,
                centerline_base_path,
                ch2_brightness_base_path,
                num_frames,
                sample_length=sample_length,
                mask_path_fn=mask_path_fn,
                image_ext=self.detected_ext,
            )
            ch2_kymo_path = generate_kymograph(
                ch2_fname,
                ch2_brightness_base_path,
                num_frames,
                str(output_dir),
                fig_size=(self.fig_width_spin.value(), self.fig_height_spin.value()),
                line_width=line_width,
                labsize=labsize,
                pixel_per_micron=pixel_per_micron,
                adjust_color_range=adjust_color_range,
                time_interval_sec=time_interval_sec,
                axis_unit=axis_unit,
            )
            merged_path = merge_kymograph(
                brightness_base_path,
                ch2_brightness_base_path,
                num_frames,
                str(output_dir),
                fig_size=(self.fig_width_spin.value(), self.fig_height_spin.value()),
                line_width=line_width,
                labsize=labsize,
                pixel_per_micron=pixel_per_micron,
                adjust_color_range=adjust_color_range,
                color1=color1,
                color2=color2,
                time_interval_sec=time_interval_sec,
                axis_unit=axis_unit,
            )
            return {"Channel 1": kymo_path, "Channel 2": ch2_kymo_path, "Merged": merged_path}

        return task

    def on_task_finished(self, result) -> None:
        if not result:
            return
        self._preview_results = result
        combo = self.preview_channel_combo
        combo.blockSignals(True)
        previous = combo.currentText()
        combo.clear()
        combo.addItems(result.keys())
        select = previous if previous in result else ("Merged" if "Merged" in result else next(iter(result)))
        combo.setCurrentText(select)
        combo.blockSignals(False)
        self._render_preview(select)

    def _render_preview(self, channel_name: str) -> None:
        results = getattr(self, "_preview_results", None)
        if not results or channel_name not in results:
            return
        import matplotlib.image as mpimg

        image = mpimg.imread(results[channel_name])
        self.preview.ax.clear()
        self.preview.ax.imshow(image)
        self.preview.ax.set_axis_off()
        self.preview.redraw()
