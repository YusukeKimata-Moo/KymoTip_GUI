"""Main window: tab-based navigation across the pipeline stages (builtin + plugins)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QMenu, QMessageBox, QTabBar, QTabWidget, QToolButton

from .plugin_loader import StageLoadError, load_all_stages
from .stages.base import StageWidgetBase
from .stages.input_preview_stage import InputPreviewStage


def _default_plugins_dir() -> Path:
    """ユーザー独自プラグイン置き場を決める。

    ソースから実行中(開発時)は、リポジトリ直下の`plugins/`(gitignore対象)。
    PyInstaller等でパッケージ化された実行ファイルとして起動している場合、
    `__file__`はインストール/展開先を指すため、Program Files配下など書き込み
    権限のない場所になりがちで、かつ再インストールで消える可能性がある。
    そのため、OSごとのユーザーデータディレクトリ配下を使う。
    """
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
        return base / "KymoTip" / "plugins"
    return Path(__file__).resolve().parents[2] / "plugins"


PLUGINS_DIR = _default_plugins_dir()


class AutoSizeTabWidget(QTabWidget):
    """QTabWidgetは既定で全タブページ中の最大サイズヒントを常に確保するため、
    非表示のタブに大きな最小サイズを持つウィジェット(例: Segmentationタブの
    SAM2クリック操作用プレビューはsetMinimumHeight(500))が1つでもあると、
    そのタブを開いていなくてもウィンドウ全体の最小高さが不必要に肥大化し、
    画面に収まらずプレビューがはみ出す不具合が起きる。現在表示中のページの
    サイズヒントのみを使うようにする。
    """

    def _current_based_size(self, current_fn: str) -> QSize:
        current = self.currentWidget()
        if current is None:
            return getattr(super(), current_fn)()
        tab_bar_hint = self.tabBar().sizeHint()
        content_hint = getattr(current, current_fn)()
        width = max(content_hint.width(), tab_bar_hint.width())
        height = content_hint.height() + tab_bar_hint.height()
        return QSize(width, height)

    def minimumSizeHint(self) -> QSize:
        return self._current_based_size("minimumSizeHint")

    def sizeHint(self) -> QSize:
        return self._current_based_size("sizeHint")

    def tabInserted(self, index: int) -> None:
        super().tabInserted(index)
        self.updateGeometry()

    def tabRemoved(self, index: int) -> None:
        super().tabRemoved(index)
        self.updateGeometry()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.currentChanged.connect(lambda _index: self.updateGeometry())


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("KymoTip")
        self.resize(1200, 800)

        self.input_preview_stage = InputPreviewStage(on_apply_project=self._apply_project_settings)
        # ユーザーがすぐそこにプラグインフォルダを置けるよう、未作成なら起動時に
        # 作っておく(権限等で失敗しても起動は継続する)。
        try:
            PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        builtin_stages, self.plugin_stages, load_errors = load_all_stages(PLUGINS_DIR)
        # wire_projectはビルトイン・プラグイン両方に反映する必要があるため、
        # タブ表示の有無に関わらず全ステージをここで保持する。
        self.stages = builtin_stages + self.plugin_stages

        self.tabs = AutoSizeTabWidget()
        self.tabs.setTabsClosable(True)
        # 組み込みタブには閉じるボタンを出さない(プラグインタブのみ閉じられる)。
        self.tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self.tabs.addTab(self.input_preview_stage, "0. Input Preview")
        self._hide_close_button(0)
        for index, stage in enumerate(builtin_stages, start=1):
            label = stage.tab_label or stage.stage_title
            self.tabs.addTab(stage, f"{index}. {label}")
            self._hide_close_button(self.tabs.count() - 1)

        self._plugin_actions: dict[StageWidgetBase, QAction] = {}
        self._build_plugin_menu()

        self.setCentralWidget(self.tabs)

        if load_errors:
            self._warn_load_errors(load_errors)

    def _hide_close_button(self, index: int) -> None:
        self.tabs.tabBar().setTabButton(index, QTabBar.RightSide, None)

    def _build_plugin_menu(self) -> None:
        # ツールバーに置くと目立たず気づかれにくいため、タブバーの右端
        # (コーナー)に大きめ・太字のボタンとして配置する。
        button = QToolButton()
        button.setObjectName("pluginsButton")
        button.setText("+ Plugins")
        button.setToolButtonStyle(Qt.ToolButtonTextOnly)
        button.setPopupMode(QToolButton.InstantPopup)

        menu = QMenu(button)
        for stage in self.plugin_stages:
            label = stage.tab_label or stage.stage_title
            action = QAction(label, menu, checkable=True)
            action.toggled.connect(lambda checked, s=stage: self._on_plugin_toggled(s, checked))
            menu.addAction(action)
            self._plugin_actions[stage] = action
        button.setMenu(menu)
        if not self.plugin_stages:
            button.setEnabled(False)
            button.setToolTip("No plugins found in plugins/")

        self.tabs.setCornerWidget(button, Qt.TopRightCorner)

    def _on_plugin_toggled(self, stage: StageWidgetBase, checked: bool) -> None:
        if checked:
            if self.tabs.indexOf(stage) != -1:
                return
            label = stage.tab_label or stage.stage_title
            index = self.tabs.addTab(stage, label)
            self.tabs.setCurrentIndex(index)
        else:
            index = self.tabs.indexOf(stage)
            if index != -1:
                self.tabs.removeTab(index)

    def _on_tab_close_requested(self, index: int) -> None:
        widget = self.tabs.widget(index)
        action = self._plugin_actions.get(widget)
        if action is None:
            # 組み込みタブは閉じるボタンを出していないので基本ここには来ないが、
            # 念のため何もしない。
            return
        # setChecked(False)がtoggledシグナル経由で_on_plugin_toggledを呼び、
        # そちらでタブを除去するので、ここでは状態を合わせるだけでよい。
        action.setChecked(False)

    def _warn_load_errors(self, errors: list[StageLoadError]) -> None:
        lines = "\n".join(f"- {err}" for err in errors)
        QMessageBox.warning(
            self,
            "Stage/Plugin load warnings",
            "Some stages or plugins failed to load and were skipped:\n" + lines,
        )

    def _apply_project_settings(self, base_dir: str, fname: str) -> None:
        base = Path(base_dir)
        self.input_preview_stage.input_dir_picker.set_path(str(base / "00_raw"))
        for stage in self.stages:
            try:
                stage.wire_project(base, fname)
            except Exception as exc:
                stage.log(f"[wire_project] Error: {exc}")
