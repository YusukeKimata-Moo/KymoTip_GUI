"""GUIウィジェットが例外なくインスタンス化できることだけを確認するスモークテスト。

実際の画面表示・クリック操作の検証はユーザー自身が`python -m kymotip.gui.main`を
起動して行う(このテストはウィンドウを表示しない)。
"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    import kymotip.gui  # noqa: F401  (WindowsでのQt DLL事前ロードを発動させる)
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_instantiates(qapp):
    from kymotip.gui.main_window import MainWindow

    window = MainWindow()
    assert window.windowTitle() == "KymoTip"


def test_all_stage_widgets_instantiate(qapp):
    from kymotip.gui.stages.centerline_stage import CenterlineStage
    from kymotip.gui.stages.contour_stage import ContourStage
    from kymotip.gui.stages.input_preview_stage import InputPreviewStage
    from kymotip.gui.stages.kymograph_stage import KymographStage
    from kymotip.gui.stages.registration_stage import RegistrationStage
    from kymotip.gui.stages.segmentation_stage import SegmentationStage
    from kymotip.gui.stages.trajectory_stage import TrajectoryStage

    for cls in (
        InputPreviewStage,
        RegistrationStage,
        SegmentationStage,
        ContourStage,
        TrajectoryStage,
        CenterlineStage,
        KymographStage,
    ):
        widget = cls()
        assert widget.stage_title
