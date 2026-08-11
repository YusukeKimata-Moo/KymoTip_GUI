"""PreviewCanvasにフレーム送りスライダーを付加した共通プレビューウィジェット。

既存コードとの後方互換のため、ax/show_image/redraw/clearは内部のPreviewCanvasへ
そのまま委譲する(単一フレームだけ表示する既存の呼び出しは変更不要)。
複数フレームをスライダーで閲覧したい場合はset_frames()を呼ぶ。
"""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSlider, QVBoxLayout, QWidget

from .preview import PreviewCanvas


class FrameBrowser(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = PreviewCanvas()

        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self._on_slider_changed)

        self.frame_label = QLabel("")

        slider_row = QHBoxLayout()
        slider_row.addWidget(self.slider, stretch=1)
        slider_row.addWidget(self.frame_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas, stretch=1)
        layout.addLayout(slider_row)

        self._render_fn: Callable[[int], None] | None = None
        self._num_frames = 0

    # --- PreviewCanvasへの委譲(既存呼び出し互換) ---
    @property
    def ax(self):
        return self.canvas.ax

    def show_image(self, image, cmap: str = "gray") -> None:
        self.canvas.show_image(image, cmap=cmap)

    def redraw(self) -> None:
        self.canvas.redraw()

    def clear(self) -> None:
        self.canvas.clear()

    # --- スライダーによる複数フレーム閲覧 ---
    def set_frames(self, num_frames: int, render_fn: Callable[[int], None]) -> None:
        """0〜num_frames-1をスライダーで切り替えるたびにrender_fn(index)を呼ぶ。"""
        self._render_fn = render_fn
        self._num_frames = num_frames

        self.slider.blockSignals(True)
        self.slider.setMaximum(max(num_frames - 1, 0))
        self.slider.setEnabled(num_frames > 1)
        self.slider.setValue(0)
        self.slider.blockSignals(False)

        if num_frames > 0:
            self._render(0)
        else:
            self.canvas.clear()
            self.frame_label.setText("No frames")

    def refresh_current(self) -> None:
        """現在のスライダー位置のまま再描画する(プレビュー対象の切り替え時などに使う)。"""
        self._render(self.slider.value())

    def _on_slider_changed(self, value: int) -> None:
        self._render(value)

    def _render(self, index: int) -> None:
        self.frame_label.setText(f"Frame {index + 1} / {self._num_frames}")
        if self._render_fn is not None:
            self._render_fn(index)
