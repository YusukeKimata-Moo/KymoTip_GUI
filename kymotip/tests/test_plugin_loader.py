"""ステージ/プラグインの自動検出とフォールト分離の挙動を確認するテスト。"""
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")


@pytest.fixture(scope="module")
def qapp():
    import kymotip.gui  # noqa: F401
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


def test_discover_builtin_stage_classes_finds_all_seven():
    from kymotip.gui.plugin_loader import discover_builtin_stage_classes

    classes, errors = discover_builtin_stage_classes()
    assert errors == []
    orders = sorted(cls.plugin_order for cls in classes)
    assert orders == [1, 2, 3, 4, 5, 6, 7]


def test_broken_plugin_is_skipped_without_crashing(tmp_path):
    from kymotip.gui.plugin_loader import discover_plugin_stage_classes

    plugin_dir = tmp_path / "broken_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text(
        "raise RuntimeError('intentionally broken for test')\n", encoding="utf-8"
    )

    classes, errors = discover_plugin_stage_classes(tmp_path)

    assert classes == []
    assert len(errors) == 1
    assert "intentionally broken for test" in errors[0].message


def test_valid_plugin_alongside_broken_plugin_is_still_loaded(tmp_path):
    from kymotip.gui.plugin_loader import discover_plugin_stage_classes

    broken_dir = tmp_path / "broken_plugin"
    broken_dir.mkdir()
    (broken_dir / "__init__.py").write_text("raise RuntimeError('boom')\n", encoding="utf-8")

    ok_dir = tmp_path / "ok_plugin"
    ok_dir.mkdir()
    (ok_dir / "__init__.py").write_text(
        "from kymotip.plugin_api import StageWidgetBase\n"
        "\n"
        "class OkStage(StageWidgetBase):\n"
        "    stage_title = 'Ok'\n"
        "    plugin_order = 100\n",
        encoding="utf-8",
    )

    classes, errors = discover_plugin_stage_classes(tmp_path)

    assert [cls.__name__ for cls in classes] == ["OkStage"]
    assert len(errors) == 1
    assert "boom" in errors[0].message


def test_folder_plugin_with_relative_import_is_loaded(tmp_path):
    from kymotip.gui.plugin_loader import discover_plugin_stage_classes

    plugin_dir = tmp_path / "cell_shape_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "helper.py").write_text(
        "def compute_area(mask):\n    return mask.sum()\n",
        encoding="utf-8",
    )
    (plugin_dir / "__init__.py").write_text(
        "from kymotip.plugin_api import StageWidgetBase\n"
        "from .helper import compute_area\n"
        "\n"
        "class FolderStage(StageWidgetBase):\n"
        "    stage_title = 'Folder plugin'\n"
        "    plugin_order = 2.5\n"
        "    compute_area = staticmethod(compute_area)\n",
        encoding="utf-8",
    )

    classes, errors = discover_plugin_stage_classes(tmp_path)

    assert errors == []
    assert [cls.__name__ for cls in classes] == ["FolderStage"]


def test_folder_without_init_py_is_ignored(tmp_path):
    from kymotip.gui.plugin_loader import discover_plugin_stage_classes

    (tmp_path / "not_a_plugin").mkdir()
    (tmp_path / "not_a_plugin" / "notes.txt").write_text("memo", encoding="utf-8")

    classes, errors = discover_plugin_stage_classes(tmp_path)

    assert classes == []
    assert errors == []


def test_incompatible_api_version_is_skipped_as_error(qapp, tmp_path):
    from kymotip.gui.plugin_loader import instantiate_stages
    from kymotip.plugin_api import StageWidgetBase

    class IncompatibleStage(StageWidgetBase):
        stage_title = "Incompatible"
        plugin_order = 1
        plugin_api_version = 999

    instances, errors = instantiate_stages([IncompatibleStage])

    assert instances == []
    assert len(errors) == 1
    assert "plugin_api_version" in errors[0].message


def test_load_all_stages_ignores_missing_plugins_dir(qapp, tmp_path):
    from kymotip.gui.plugin_loader import load_all_stages

    builtin_stages, plugin_stages, errors = load_all_stages(tmp_path / "does_not_exist")

    assert errors == []
    assert [stage.plugin_order for stage in builtin_stages] == [1, 2, 3, 4, 5, 6, 7]
    assert plugin_stages == []


def test_load_all_stages_separates_builtin_and_plugin_stages(qapp, tmp_path):
    from kymotip.gui.plugin_loader import load_all_stages

    plugin_dir = tmp_path / "ok_plugin"
    plugin_dir.mkdir()
    (plugin_dir / "__init__.py").write_text(
        "from kymotip.plugin_api import StageWidgetBase\n"
        "\n"
        "class OkStage(StageWidgetBase):\n"
        "    stage_title = 'Ok'\n"
        "    plugin_order = 2.5\n",
        encoding="utf-8",
    )

    builtin_stages, plugin_stages, errors = load_all_stages(tmp_path)

    assert errors == []
    assert [stage.plugin_order for stage in builtin_stages] == [1, 2, 3, 4, 5, 6, 7]
    assert [type(stage).__name__ for stage in plugin_stages] == ["OkStage"]


def test_non_numeric_plugin_order_is_skipped_without_crashing(qapp):
    from kymotip.gui.plugin_loader import instantiate_stages
    from kymotip.plugin_api import StageWidgetBase

    class BadOrderStage(StageWidgetBase):
        stage_title = "Bad order"
        plugin_order = "late"  # type: ignore[assignment]

    class GoodStage(StageWidgetBase):
        stage_title = "Good"
        plugin_order = 1

    instances, errors = instantiate_stages([BadOrderStage, GoodStage])

    assert [type(stage) for stage in instances] == [GoodStage]
    assert len(errors) == 1
    assert "plugin_order" in errors[0].message


def test_builtin_stages_survive_plugin_api_version_bump(qapp, monkeypatch):
    from kymotip.gui import plugin_loader

    monkeypatch.setattr(plugin_loader, "PLUGIN_API_VERSION", 999)

    classes, _discover_errors = plugin_loader.discover_builtin_stage_classes()
    instances, errors = plugin_loader.instantiate_stages(classes)

    assert errors == []
    assert len(instances) == 7
