"""KymoTip GUI entry point. Run with `python -m kymotip.gui.main`."""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .main_window import MainWindow
from .style import STYLESHEET


def _app_icon_path() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parents[2]
    return base_dir / "packaging" / "icons" / "kymotip.png"


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("KymoTip")
    app.setOrganizationName("KymoTip")
    app_icon = QIcon(str(_app_icon_path()))
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)
    # OSネイティブのウィジェット外観(Windowsテーマ等)に依存せず、フラットな
    # 見た目のQSSを確実に適用するため、ベーススタイルをFusionに固定する。
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    if not app_icon.isNull():
        window.setWindowIcon(app_icon)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
