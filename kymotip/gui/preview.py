"""matplotlibをQtに埋め込むプレビュー用ウィジェット。"""
from __future__ import annotations

from matplotlib.axes import Axes
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

# Figure(外枠)はGUIのダークテーマに合わせた暗い色、Axes(実際のプロット/
# 画像が占める領域)は白のままにする。これにより、出力される画像の実際の
# サイズが白い領域として周囲の暗い余白から一目でわかる。
# ここで決める色はこのプレビューウィジェット専用で、matplotlibのrcParams
# には触れない(kymotip/core/*.pyが保存する実際の解析結果画像の配色に
# 影響させないため)。
_FIGURE_BG = "#1a1b1e"
_AXES_BG = "#ffffff"
_LABEL_FG = "#c7c9cd"


class _PreviewAxes(Axes):
    """clear()を呼ばれるたびに、プレビュー用の配色(白背景+明るい文字色)を
    保つAxes。各ステージが`self.preview.ax.clear()`を直接呼んでから
    plot/imshowするため、呼び出し側を変更せずに配色を維持できるようにする。
    """

    def clear(self) -> None:
        super().clear()
        self._apply_preview_style()

    def _apply_preview_style(self) -> None:
        self.set_facecolor(_AXES_BG)
        self.tick_params(colors=_LABEL_FG)
        self.xaxis.label.set_color(_LABEL_FG)
        self.yaxis.label.set_color(_LABEL_FG)
        for spine in self.spines.values():
            spine.set_color(_LABEL_FG)


class PreviewCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.figure = Figure(figsize=(5, 4), facecolor=_FIGURE_BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        # FigureCanvasQTAggはsizeHint()が描画のたびにfigureのピクセルサイズを
        # 返すため、既定のExpandingポリシーのままだとdraw()の度にレイアウトへ
        # 拡大要求が伝播し、パネルからはみ出す(ウィンドウの最小化/最大化を
        # するまで直らない)不具合が起きる。Ignoredにして親レイアウト(splitter)
        # が決めたサイズに常に従わせる。
        self.canvas.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.ax = self.figure.add_subplot(111, axes_class=_PreviewAxes)
        self.ax._apply_preview_style()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

    def clear(self) -> None:
        self.ax.clear()
        self.canvas.draw_idle()

    def show_image(self, image, cmap: str = "gray") -> None:
        self.ax.clear()
        self.ax.imshow(image, cmap=cmap)
        self.ax.set_axis_off()
        self.canvas.draw_idle()

    def redraw(self) -> None:
        self.canvas.draw_idle()
