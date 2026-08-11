"""全ステージ共通のパネルレイアウト(入出力dir選択・パラメータフォーム領域・
実行ボタン・進捗バー・ログパネル・プレビュー)を提供するベースクラス。

各ステージウィジェットはこれを継承し、`build_parameter_form()`で
パラメータ入力欄を追加し、`run()`で実際の処理を実装する。
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
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
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from ..frame_browser import FrameBrowser
from ..settings import AppSettings
from ..workers import run_in_background


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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.input_dir_picker = DirPicker("input directory")
        self.output_dir_picker = DirPicker("output directory")

        self.form_layout = QFormLayout()
        self.form_layout.addRow("Input directory", self.input_dir_picker)
        self.form_layout.addRow("Output directory", self.output_dir_picker)

        self.build_parameter_form(self.form_layout)

        param_box = QGroupBox(self.stage_title)
        param_box.setLayout(self.form_layout)

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

        base_dir = AppSettings().project_base_dir
        if not base_dir or not fname:
            return None
        return read_reference_image_size(base_dir, fname)

    def log(self, message: str) -> None:
        self.log_view.appendPlainText(message)

    def ensure_output_dir(self) -> Path:
        output_dir = Path(self.output_dir_picker.path())
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _on_run_clicked(self) -> None:
        try:
            task = self.build_task()
        except Exception as exc:
            QMessageBox.warning(self, "Invalid input", str(exc))
            return

        self.run_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.log(f"[{self.stage_title}] Started.")

        self._thread, self._worker = run_in_background(
            task, self._on_task_finished, self._on_task_error
        )

    def build_task(self):
        """サブクラスで、引数なしのcallable(バックグラウンドスレッドで実行)を返す。"""
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
