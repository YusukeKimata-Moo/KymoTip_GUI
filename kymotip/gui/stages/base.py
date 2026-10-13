"""全ステージ共通のパネルレイアウト(入出力dir選択・パラメータフォーム領域・
実行ボタン・進捗バー・ログパネル・プレビュー)を提供するベースクラス。

各ステージウィジェットはこれを継承し、`build_parameter_form()`で
パラメータ入力欄を追加し、`run()`で実際の処理を実装する。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..frame_browser import FrameBrowser
from ..workers import run_in_background
from ...history import HistoryError, RecordedRun, TaskSpec, series_info


class DirPicker(QWidget):
    # ユーザーがテキスト編集またはBrowseボタンでパスを指定したときに発火する
    # (setPath()等プログラムからの変更では発火しない)。呼び出し元で
    # 「ユーザーが手動で指定したかどうか」を判定するのに使う。
    pathEdited = Signal(str)

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.edit = QLineEdit()
        self.edit.textEdited.connect(self.pathEdited)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self._browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        layout.addWidget(browse_button)
        self._label = label

    def _browse(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, f"Select {self._label}", self.path())
        if directory:
            self.edit.setText(directory)
            self.pathEdited.emit(directory)

    def path(self) -> str:
        return self.edit.text().strip()

    def set_path(self, value: str) -> None:
        self.edit.setText(value)


class StageWidgetBase(QWidget):
    stage_title = "Stage"

    # プラグイン(追加ステージ)として自動検出させたいサブクラスは、これらを
    # 明示的に上書きする。plugin_orderがNone(既定)のクラスはタブに追加されない。
    # plugin_api_versionはkymotip.plugin_api.PLUGIN_API_VERSIONとの整合性チェックに使う。
    plugin_order: float | None = None
    plugin_api_version: int = 1
    # タブ見出しに使う短い表示名。Noneならstage_titleをそのまま使う。
    tab_label: str | None = None
    history_name: str | None = None
    plugin_version: str | None = None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._project_base = ""
        self._project_prefix = ""

        self.input_dir_picker = DirPicker("input directory")
        self.output_dir_picker = DirPicker("output directory")

        self.form_layout = QFormLayout()
        self.form_layout.addRow("Input directory", self.input_dir_picker)
        self.form_layout.addRow("Output directory", self.output_dir_picker)

        self.build_parameter_form(self.form_layout)

        param_box = QGroupBox(self.stage_title)
        param_box.setLayout(self.form_layout)
        self.parameter_panel = param_box

        self.run_button = QPushButton("Run")
        self.run_button.setObjectName("runButton")
        self.run_button.clicked.connect(self._on_run_clicked)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(2000)

        self.preview = FrameBrowser()

        # param_boxはラジオボタンで動的に行が増減する(01 Registrationの
        # 多チャンネルモード等)ため、そのままleft_layoutに積むとフォームの
        # 最小高さがそのままQMainWindow全体の最小高さまで伝播し、ディスプレイ
        # からはみ出す。QScrollAreaで包んで、はみ出す分はスクロールで吸収する。
        param_scroll = QScrollArea()
        param_scroll.setWidgetResizable(True)
        param_scroll.setFrameShape(QFrame.NoFrame)
        param_scroll.setWidget(param_box)

        left_panel = QWidget()
        # ラジオボタン等の長いラベルがあると左パネルのsizeHintが肥大化し、
        # splitterがプレビュー側を必要以上に狭く割り当ててしまう(03 Contourで
        # 顕著)。上限を設けてプレビュー側の幅を確保する。
        left_panel.setMaximumWidth(480)
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(param_scroll)
        left_layout.addWidget(self.run_button)
        left_layout.addWidget(self.progress_bar)
        left_layout.addWidget(QLabel("Log"))
        left_layout.addWidget(self.log_view, stretch=1)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(left_panel)
        self.splitter.addWidget(self.preview)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        # タブが一度も表示されないうちはsplitterに実サイズが割り当てられず、
        # プレビューcanvasへのresizeEventが発火しないまま初回描画されてしまう
        # (結果、ウィンドウを最小化/最大化するまで表示がはみ出す)。明示的に
        # 初期サイズを与えて、初回表示前からジオメトリを確定させる。
        self.splitter.setSizes([300, 700])

        outer_layout = QVBoxLayout(self)
        outer_layout.addWidget(self.splitter)

        self._thread = None
        self._worker = None
        self.detected_ext = "png"

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        """サブクラスでパラメータ入力欄を追加する。既定では何も追加しない。"""

    def wire_project(self, base_dir: Path, fname: str) -> None:
        """プロジェクトの「Apply to All Stages」実行時に、base_dir配下の規約に
        沿った入出力ディレクトリとファイル名prefixをこのステージへ反映する。
        既定では何もしない(サブクラスで必要な範囲だけ上書きする)。
        """

    def set_project_context(self, base_dir: str | Path, fname: str) -> None:
        """Set history context independently of a plugin's wire_project override."""
        self._project_base = str(Path(base_dir).resolve()) if str(base_dir).strip() else ""
        self._project_prefix = fname

    def add_auto_detect_button(
        self, form_layout: QFormLayout, fname_edit: QLineEdit, num_frames_spin
    ) -> None:
        """入力ディレクトリ内のファイル名から「File name prefix」「Number of frames」
        (と拡張子)を自動検出するボタンを追加する。
        """
        button = QPushButton("Auto-detect from input directory")
        button.clicked.connect(lambda: self._auto_detect(fname_edit, num_frames_spin))
        form_layout.addRow(button)

    def _auto_detect(self, fname_edit: QLineEdit, num_frames_spin) -> None:
        from ...core.io_utils import discover_frames

        input_dir = self.input_dir_picker.path()
        if not input_dir:
            QMessageBox.warning(self, "Invalid input", "Input directory is required.")
            return

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
        fname_edit.setText(prefix)
        num_frames_spin.setValue(num_frames)
        self.log(f"Auto-detected: prefix='{prefix}', ext='{ext}', frames={num_frames}")

    def get_reference_image_size(self, fname: str) -> tuple[int, int] | None:
        """プレビューの座標プロット軸を固定するための基準画像サイズ(width, height)を、
        プロジェクトのbase_dir配下の01_registration出力から取得する。見つからなければNone。
        """
        from ...core.io_utils import read_reference_image_size

        base_dir = self._project_base
        if not base_dir or not fname:
            return None
        return read_reference_image_size(base_dir, fname)

    def log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def ensure_output_dir(self) -> Path:
        selected = self.output_dir_picker.path()
        if not selected:
            raise ValueError("Output directory is required.")
        output_dir = Path(selected).resolve()
        if self._project_base and output_dir == Path(self._project_base):
            raise ValueError("Choose an output subfolder separate from the project base directory.")
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _legacy_task_spec(self, task) -> TaskSpec:
        """Best-effort UI snapshot; never label a legacy callable as complete."""
        if not callable(task):
            raise TypeError("build_task() must return a TaskSpec or a callable.")
        values = {}
        visited = set()

        def collect(owner, prefix=""):
            for name, widget in vars(owner).items():
                if name.startswith("_") or not isinstance(widget, QWidget) or id(widget) in visited:
                    continue
                if not self.parameter_panel.isAncestorOf(widget):
                    continue
                visited.add(id(widget))
                key = prefix + name
                if isinstance(widget, DirPicker):
                    values[key] = widget.path()
                elif isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    values[key] = widget.value()
                elif isinstance(widget, (QCheckBox, QRadioButton)):
                    values[key] = widget.isChecked()
                elif isinstance(widget, QComboBox):
                    label = widget.currentText()
                    values[key] = label if label.isascii() else {"selected_index": widget.currentIndex()}
                elif isinstance(widget, QLineEdit):
                    if widget.echoMode() == QLineEdit.Normal:
                        values[key] = widget.text()
                else:
                    collect(widget, key + ".")

        collect(self)
        inputs = [series_info(self.input_dir_picker.path(), role="input")] if self.input_dir_picker.path() else []
        outputs = [series_info(self.output_dir_picker.path(), role="output")] if self.output_dir_picker.path() else []
        return TaskSpec(lambda context: task(), values, inputs, outputs, capture_mode="ui_snapshot_only")

    def _on_run_clicked(self) -> None:
        if not self.run_button.isEnabled():
            return
        try:
            if not self._project_base or not Path(self._project_base).is_dir():
                raise HistoryError("Set a valid project base directory in Input Preview and click Apply to All Stages.")
            task = self.build_task()
            spec = task if isinstance(task, TaskSpec) else self._legacy_task_spec(task)
            if spec.capture_mode == "ui_snapshot_only":
                self.log("History: legacy plugin UI snapshot only; hidden parameters may be unavailable.")
            stage_class = type(self)
            stage_name = self.history_name or self.stage_title
            if not stage_name.isascii():
                stage_name = stage_class.__name__
            recorded = RecordedRun(
                spec, self._project_base, self._project_prefix,
                stage_id=f"{stage_class.__module__}.{stage_class.__name__}",
                stage_name=stage_name,
                stage_kind="builtin" if stage_class.__module__.startswith("kymotip.gui.stages.") else "plugin",
                plugin_version=self.plugin_version,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return

        self.run_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log(f"[{self.stage_title}] Started.")

        try:
            self._thread, self._worker = run_in_background(
                recorded, self._on_task_finished, self._on_task_error
            )
        except Exception as exc:
            try:
                recorded.finish("failed")
            except Exception as history_error:
                exc = HistoryError(f"{exc}\nHistory could not be saved: {history_error}")
            self._on_task_error(str(exc))

    def build_task(self):
        """Return TaskSpec; legacy zero-argument callables remain supported."""
        raise NotImplementedError

    def on_task_finished(self, result) -> None:
        """サブクラスでプレビュー更新等を行う(既定では何もしない)。"""

    def _on_task_finished(self, result) -> None:
        self.run_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log(f"[{self.stage_title}] Finished.")
        self.on_task_finished(result)

    def _on_task_error(self, message: str) -> None:
        self.run_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.log(f"[{self.stage_title}] Error: {message}")
        QMessageBox.critical(self, "Error", message)
