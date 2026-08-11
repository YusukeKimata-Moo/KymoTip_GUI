"""Stage 1: Image registration panel."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...core.registration import ChannelSpec, run_registration
from .base import DirPicker, StageWidgetBase


class RegistrationStage(StageWidgetBase):
    stage_title = "Registration"
    plugin_order = 1

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.reset_extra_channel_customization()
        self.fname_edit.setText(fname)
        self.input_dir_picker.set_path(str(base_dir / "00_raw"))
        self.output_dir_picker.set_path(str(base_dir / "01_registration"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.fname_edit = QLineEdit()
        self.fname_edit.textChanged.connect(self._update_extra_channel_fnames)
        form_layout.addRow("File name prefix (reference channel)", self.fname_edit)

        self.input_dir_picker.edit.textChanged.connect(
            lambda text: self._update_extra_channel_dirs("input_dir_picker", text)
        )
        self.output_dir_picker.edit.textChanged.connect(
            lambda text: self._update_extra_channel_dirs("output_dir_picker", text)
        )

        mode_widget = QWidget()
        mode_layout = QVBoxLayout(mode_widget)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        self.ch1_radio = QRadioButton("1 channel")
        self.ch2_radio = QRadioButton("2 channels")
        self.ch3_radio = QRadioButton("3 channels")
        self.ch1_radio.setChecked(True)
        for radio in (self.ch1_radio, self.ch2_radio, self.ch3_radio):
            radio.toggled.connect(self._update_channel_visibility)
            mode_layout.addWidget(radio)
        form_layout.addRow("Number of channels", mode_widget)

        # 2ch/3ch目は、基準チャンネル(input_dir_picker/output_dir_picker/fname_edit)で
        # 求めた回転・平行移動量をそのまま適用するだけなので、入出力ディレクトリと
        # ファイル名prefixのみを追加で受け取る。
        self.ch2_group = self._build_extra_channel_group("Channel 2")
        form_layout.addRow(self.ch2_group)
        self.ch3_group = self._build_extra_channel_group("Channel 3")
        form_layout.addRow(self.ch3_group)
        self.ch2_group.setVisible(False)
        self.ch3_group.setVisible(False)

        self.angs_spin = QDoubleSpinBox()
        self.angs_spin.setRange(-360, 360)
        self.angs_spin.setValue(-5)
        form_layout.addRow("Start angle (deg)", self.angs_spin)

        self.ange_spin = QDoubleSpinBox()
        self.ange_spin.setRange(-360, 360)
        self.ange_spin.setValue(5)
        form_layout.addRow("End angle (deg)", self.ange_spin)

        self.dtheta_spin = QDoubleSpinBox()
        self.dtheta_spin.setRange(0.01, 360)
        self.dtheta_spin.setValue(1)
        form_layout.addRow("Angle step (deg)", self.dtheta_spin)

        self.start_t_spin = QSpinBox()
        self.start_t_spin.setRange(0, 100000)
        form_layout.addRow("Start frame", self.start_t_spin)

        self.num_t_spin = QSpinBox()
        self.num_t_spin.setRange(1, 100000)
        self.num_t_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_t_spin)

        self.add_auto_detect_button(form_layout, self.fname_edit, self.num_t_spin)

        self.d_spin = QSpinBox()
        self.d_spin.setRange(0, 10000)
        self.d_spin.setValue(0)
        form_layout.addRow("Reference refresh interval (d)", self.d_spin)

        self.n_fill_spin = QSpinBox()
        self.n_fill_spin.setRange(0, 255)
        form_layout.addRow("Noise fill range (n_fill)", self.n_fill_spin)

        self.preview_channel_combo = QComboBox()
        self.preview_channel_combo.currentTextChanged.connect(self._on_preview_channel_changed)
        form_layout.addRow("Preview channel", self.preview_channel_combo)

    def _build_extra_channel_group(self, title: str) -> QGroupBox:
        group = QGroupBox(title)
        layout = QFormLayout(group)
        input_picker = DirPicker(f"{title} input directory")
        output_picker = DirPicker(f"{title} output directory")
        fname_edit = QLineEdit()
        # ユーザーがファイル名prefix/ディレクトリを手動指定したら、以後は基準
        # チャンネル側の変更による自動補完で上書きしないようにするためのフラグ。
        fname_edit.fname_customized = False
        input_picker.dir_customized = False
        output_picker.dir_customized = False

        def mark_customized() -> None:
            fname_edit.fname_customized = True

        fname_edit.textEdited.connect(mark_customized)
        input_picker.pathEdited.connect(lambda _text: setattr(input_picker, "dir_customized", True))
        output_picker.pathEdited.connect(lambda _text: setattr(output_picker, "dir_customized", True))
        layout.addRow("Input directory", input_picker)
        layout.addRow("Output directory", output_picker)
        layout.addRow("File name prefix", fname_edit)
        group.input_dir_picker = input_picker
        group.output_dir_picker = output_picker
        group.fname_edit = fname_edit
        return group

    def reset_extra_channel_customization(self) -> None:
        """プロジェクト設定の再適用(Apply project settings)前に呼び出し、
        Channel 2/3のカスタマイズ済みフラグを解除する。呼ばないと、以前の
        プロジェクトで手動編集した値が新プロジェクトに切り替えても残り続け、
        旧プロジェクトのパスを誤って使い続けてしまう。
        """
        for group in (self.ch2_group, self.ch3_group):
            group.fname_edit.fname_customized = False
            group.input_dir_picker.dir_customized = False
            group.output_dir_picker.dir_customized = False

    def _update_extra_channel_fnames(self, fname: str) -> None:
        for group, suffix in ((self.ch2_group, "_ch2"), (self.ch3_group, "_ch3")):
            fname_edit = group.fname_edit
            if not fname_edit.fname_customized:
                fname_edit.setText(f"{fname}{suffix}" if fname else "")

    def _update_extra_channel_dirs(self, picker_attr: str, base_path: str) -> None:
        base_path = base_path.strip()
        for group, suffix in ((self.ch2_group, "_ch2"), (self.ch3_group, "_ch3")):
            picker = getattr(group, picker_attr)
            if picker.dir_customized:
                continue
            if not base_path:
                picker.set_path("")
                continue
            path = Path(base_path)
            picker.set_path(str(path.parent / f"{path.name}{suffix}"))

    def _update_channel_visibility(self) -> None:
        self.ch2_group.setVisible(self.ch2_radio.isChecked() or self.ch3_radio.isChecked())
        self.ch3_group.setVisible(self.ch3_radio.isChecked())

    def _extra_channel_spec(self, group: QGroupBox) -> ChannelSpec:
        input_dir = group.input_dir_picker.path()
        output_dir = group.output_dir_picker.path()
        fname = group.fname_edit.text().strip()
        if not (input_dir and output_dir and fname):
            raise ValueError(f"{group.title()}: input/output directory and file name prefix are required.")
        return ChannelSpec(input_dir=input_dir, output_dir=output_dir, fname=fname, ext=self.detected_ext)

    def build_task(self):
        fname = self.fname_edit.text().strip()
        if not fname:
            raise ValueError("File name prefix is required.")
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            raise ValueError("Input directory is required.")
        output_dir = self.output_dir_picker.path()
        if not output_dir:
            raise ValueError("Output directory is required.")

        channels = [ChannelSpec(input_dir=input_dir, output_dir=output_dir, fname=fname, ext=self.detected_ext)]
        if self.ch2_radio.isChecked() or self.ch3_radio.isChecked():
            channels.append(self._extra_channel_spec(self.ch2_group))
        if self.ch3_radio.isChecked():
            channels.append(self._extra_channel_spec(self.ch3_group))
        self._preview_channels = channels

        angs = self.angs_spin.value()
        ange = self.ange_spin.value()
        dtheta = self.dtheta_spin.value()
        start_t = self.start_t_spin.value()
        num_t = self.num_t_spin.value()
        d = self.d_spin.value()
        n_fill = self.n_fill_spin.value()

        def task():
            run_registration(
                channels=channels,
                angs=angs,
                ange=ange,
                dtheta=dtheta,
                start_t=start_t,
                num_t=num_t,
                d=d,
                n_fill=n_fill,
            )
            return output_dir

        return task

    def on_task_finished(self, result) -> None:
        from ...core.io_utils import frame_path, normalize_for_display, read_image_any

        channels = self._preview_channels
        ext = self.detected_ext
        num_frames = self.num_t_spin.value()

        combo = self.preview_channel_combo
        labels = [f"Channel {i + 1}" for i in range(len(channels))]
        combo.blockSignals(True)
        previous = combo.currentText()
        combo.clear()
        combo.addItems(labels)
        combo.setCurrentText(previous if previous in labels else labels[0])
        combo.blockSignals(False)

        def render(index: int) -> None:
            channel = channels[combo.currentIndex()]
            path = frame_path(channel.output_dir, channel.fname, index, ext)
            try:
                image = read_image_any(path)
            except Exception:
                self.preview.clear()
                return
            self.preview.show_image(normalize_for_display(image))

        self.preview.set_frames(num_frames, render)

    def _on_preview_channel_changed(self, _text: str) -> None:
        self.preview.refresh_current()
