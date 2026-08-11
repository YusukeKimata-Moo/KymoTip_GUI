"""アプリ全体の見た目(フラット・ミニマル、ダークテーマ+青アクセント)。

QSSファイルではなくPython文字列にしているのは、PyInstaller等でパッケージ化
した際に追加のデータファイル同梱設定なしで確実に読み込めるようにするため。
"""
from __future__ import annotations

# プレビュー(matplotlib)の配色はkymotip/gui/preview.pyで、このウィジェット
# 専用に(matplotlibのrcParamsを変更せず)設定している。rcParamsを変更すると
# kymotip/core/*.pyが保存する実際の解析結果画像(グラフPNG)の背景色まで
# 変わってしまうため、ここでは触らない。

STYLESHEET = """
* {
    font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
    font-size: 9.5pt;
}

QWidget {
    background-color: #1e1f22;
    color: #e3e5e8;
}

QGroupBox {
    background-color: #2b2d31;
    border: 1px solid #3f4147;
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #c7c9cd;
}

QTabWidget::pane {
    border: 1px solid #3f4147;
    border-radius: 6px;
    background-color: #2b2d31;
    top: -1px;
}
QTabBar::tab {
    background: transparent;
    color: #9a9ca3;
    padding: 7px 16px;
    margin-right: 2px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected {
    color: #f2f3f5;
    border-bottom: 2px solid #4c8dff;
    font-weight: 600;
}
QTabBar::tab:hover:!selected {
    color: #e3e5e8;
}

QPushButton {
    background-color: #35373c;
    border: 1px solid #46484f;
    border-radius: 5px;
    padding: 5px 14px;
    color: #e3e5e8;
}
QPushButton:hover {
    background-color: #3d3f45;
    border-color: #54565e;
}
QPushButton:pressed {
    background-color: #2c2e33;
}
QPushButton:disabled {
    color: #6b6d73;
    background-color: #2b2d31;
    border-color: #3a3c41;
}

QPushButton#runButton {
    background-color: #4c8dff;
    border: 1px solid #4c8dff;
    color: #10131a;
    font-weight: 600;
    padding: 7px 14px;
}
QPushButton#runButton:hover {
    background-color: #6ba0ff;
    border-color: #6ba0ff;
}
QPushButton#runButton:pressed {
    background-color: #3d78e0;
}
QPushButton#runButton:disabled {
    background-color: #35486b;
    border-color: #35486b;
    color: #7c8598;
}

QToolButton#pluginsButton {
    background-color: #2b2d31;
    border: 1px solid #4c8dff;
    border-radius: 5px;
    color: #6ba0ff;
    font-weight: 600;
    padding: 4px 12px;
}
QToolButton#pluginsButton:hover {
    background-color: #26344d;
}
QToolButton#pluginsButton:disabled {
    color: #6b6d73;
    border-color: #3a3c41;
    background-color: #2b2d31;
}

QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #232428;
    border: 1px solid #46484f;
    border-radius: 4px;
    padding: 3px 6px;
    color: #e3e5e8;
    selection-background-color: #4c8dff;
    selection-color: #10131a;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QPlainTextEdit:focus {
    border: 1px solid #4c8dff;
}
QLineEdit:disabled, QPlainTextEdit:disabled {
    background-color: #2b2d31;
    color: #6b6d73;
}

QComboBox::drop-down {
    border: none;
}

QPlainTextEdit {
    font-family: Consolas, "Courier New", monospace;
    font-size: 9pt;
    background-color: #1a1b1e;
}

QProgressBar {
    border: 1px solid #3f4147;
    border-radius: 4px;
    background-color: #2b2d31;
    text-align: center;
    height: 14px;
    color: #e3e5e8;
}
QProgressBar::chunk {
    background-color: #4c8dff;
    border-radius: 3px;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QSplitter::handle {
    background-color: #3a3c41;
}
QSplitter::handle:horizontal {
    width: 4px;
}
QSplitter::handle:vertical {
    height: 4px;
}

QLabel {
    background: transparent;
}

QRadioButton, QCheckBox {
    spacing: 6px;
    color: #e3e5e8;
}
QRadioButton::indicator, QCheckBox::indicator {
    width: 15px;
    height: 15px;
    border: 1px solid #6b6e76;
    background-color: #35373c;
}
QRadioButton::indicator {
    border-radius: 8px;
}
QCheckBox::indicator {
    border-radius: 3px;
    background-color: transparent;
}
QRadioButton::indicator:hover, QCheckBox::indicator:hover {
    border-color: #8a8d96;
}
QRadioButton::indicator:checked {
    border: 1px solid #4c8dff;
    background-color: #4c8dff;
    background-image: none;
}
QCheckBox::indicator:checked {
    border: 2px solid #eaf1ff;
    background-color: #4c8dff;
}
QRadioButton::indicator:disabled, QCheckBox::indicator:disabled {
    border-color: #46484f;
    background-color: #2b2d31;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #46484f;
    border-radius: 2px;
}
QSlider::groove:vertical {
    width: 4px;
    background: #46484f;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    width: 15px;
    height: 15px;
    margin: -6px 0;
    border-radius: 7px;
    background: #6ba0ff;
    border: 1px solid #4c8dff;
}
QSlider::handle:vertical {
    width: 15px;
    height: 15px;
    margin: 0 -6px;
    border-radius: 7px;
    background: #6ba0ff;
    border: 1px solid #4c8dff;
}
QSlider::handle:hover {
    background: #8ab4ff;
}
QSlider::sub-page:horizontal {
    background: #4c8dff;
    border-radius: 2px;
}
QSlider::add-page:vertical {
    background: #4c8dff;
    border-radius: 2px;
}

QMenu {
    background-color: #2b2d31;
    border: 1px solid #3f4147;
    border-radius: 6px;
    padding: 4px;
    color: #e3e5e8;
}
QMenu::item {
    padding: 5px 20px;
    border-radius: 4px;
}
QMenu::item:selected {
    background-color: #26344d;
    color: #6ba0ff;
}

QScrollBar:vertical {
    background: #1e1f22;
    width: 12px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #5a5d66;
    border-radius: 5px;
    min-height: 24px;
}
QScrollBar::handle:vertical:hover {
    background: #6f727c;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    background: #1e1f22;
    height: 12px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #5a5d66;
    border-radius: 5px;
    min-width: 24px;
}
QScrollBar::handle:horizontal:hover {
    background: #6f727c;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
"""
