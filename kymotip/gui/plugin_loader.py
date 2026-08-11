"""組み込みステージ(kymotip/gui/stages/)と外部プラグイン(plugins/)を自動検出し、
インスタンス化するモジュール。

1つのモジュール/クラスのimportやインスタンス化に失敗しても、その1つだけを
スキップしてアプリ全体は起動を続けられるよう、各ステップを個別にtry/exceptで
囲む(フォールト分離)。
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import pkgutil
import sys
from pathlib import Path

from ..plugin_api import PLUGIN_API_VERSION
from . import stages as builtin_stages_package
from .stages.base import StageWidgetBase

_BUILTIN_PACKAGE_PREFIX = f"{builtin_stages_package.__name__}."


class StageLoadError:
    """1件のステージ/プラグイン読み込み失敗を表す。"""

    def __init__(self, source: str, message: str) -> None:
        self.source = source
        self.message = message

    def __str__(self) -> str:
        return f"{self.source}: {self.message}"


def _iter_stage_classes_from_module(module) -> list[type[StageWidgetBase]]:
    # フォルダ形式プラグイン(__init__.py + 補助モジュール)では、StageWidgetBase
    # サブクラスが補助モジュール(例: stage.py)で定義され、__init__.pyから
    # `from .stage import MyStage` のように再exportされることがある。その場合
    # obj.__module__はパッケージ名+サブモジュール名になるため、module.__name__
    # と完全一致だけでなく、そのパッケージ配下(prefix一致)も対象に含める。
    package_prefix = module.__name__ + "."
    found = []
    for _name, obj in inspect.getmembers(module, inspect.isclass):
        if (
            issubclass(obj, StageWidgetBase)
            and obj is not StageWidgetBase
            and obj.plugin_order is not None
            and (obj.__module__ == module.__name__ or obj.__module__.startswith(package_prefix))
        ):
            found.append(obj)
    return found


def discover_builtin_stage_classes() -> tuple[list[type[StageWidgetBase]], list[StageLoadError]]:
    """kymotip/gui/stages/配下の各モジュールを走査し、plugin_orderが設定された
    StageWidgetBaseサブクラスを集める。
    """
    classes: list[type[StageWidgetBase]] = []
    errors: list[StageLoadError] = []
    package = builtin_stages_package
    for module_info in pkgutil.iter_modules(package.__path__, prefix=f"{package.__name__}."):
        try:
            module = importlib.import_module(module_info.name)
        except Exception as exc:
            errors.append(StageLoadError(module_info.name, str(exc)))
            continue
        classes.extend(_iter_stage_classes_from_module(module))
    return classes, errors


def _plugin_entry_points(plugins_dir: Path):
    """plugins_dir直下のプラグインフォルダを(モジュール名, __init__.py,
    サブモジュール検索パス)のタプルとして列挙する。

    プラグインは常にフォルダ形式(plugins/my_plugin/__init__.py)。1フォルダ
    1プラグインとし、中に複数ファイル(補助モジュール、README.md等)を
    自由に置けるようにすることで、配布時にフォルダごとコピーすれば済むように
    している(エージェントのSkillフォルダと同様の考え方)。`__init__.py`が
    無いフォルダ、および`_`で始まる名前のフォルダは無視する。
    """
    for path in sorted(plugins_dir.iterdir()):
        if not path.is_dir() or path.name.startswith("_"):
            continue
        init_path = path / "__init__.py"
        if not init_path.is_file():
            continue
        yield f"kymotip_user_plugins.{path.name}", init_path, [str(path)]


def discover_plugin_stage_classes(
    plugins_dir: Path,
) -> tuple[list[type[StageWidgetBase]], list[StageLoadError]]:
    """plugins_dir直下の、__init__.pyを持つフォルダをそれぞれ独立した
    パッケージとして読み込み、plugin_orderが設定されたStageWidgetBase
    サブクラスを集める。plugins_dirが存在しない場合は何もしない
    (ユーザーが未作成でも起動可能)。
    """
    classes: list[type[StageWidgetBase]] = []
    errors: list[StageLoadError] = []
    if not plugins_dir.is_dir():
        return classes, errors
    for module_name, entry_path, search_locations in _plugin_entry_points(plugins_dir):
        try:
            spec = importlib.util.spec_from_file_location(
                module_name, entry_path, submodule_search_locations=search_locations
            )
            if spec is None or spec.loader is None:
                raise ImportError(f"Cannot create module spec for {entry_path}")
            module = importlib.util.module_from_spec(spec)
            # dataclass等、実行中にsys.modulesから自モジュールを引く処理や、
            # プラグインフォルダ内の相対import(from . import helper)が
            # 通常のimportと同じように動くよう、exec_module前に登録する。
            sys.modules[module_name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(module_name, None)
                raise
        except Exception as exc:
            errors.append(StageLoadError(str(entry_path), str(exc)))
            continue
        classes.extend(_iter_stage_classes_from_module(module))
    return classes, errors


def instantiate_stages(
    classes: list[type[StageWidgetBase]],
) -> tuple[list[StageWidgetBase], list[StageLoadError]]:
    instances: list[StageWidgetBase] = []
    errors: list[StageLoadError] = []
    for cls in classes:
        # 組み込みステージは常にアプリ本体と同じコードから来るため、API版チェックの
        # 対象は外部プラグインのみにする。将来PLUGIN_API_VERSIONを上げたときに
        # 組み込みステージがStageWidgetBase.plugin_api_version=1のまま不一致扱いに
        # なり、パイプライン全体がタブから消えるのを防ぐ。
        is_builtin = cls.__module__.startswith(_BUILTIN_PACKAGE_PREFIX)
        if not is_builtin and cls.plugin_api_version != PLUGIN_API_VERSION:
            errors.append(
                StageLoadError(
                    cls.__module__,
                    f"{cls.__name__}: plugin_api_version={cls.plugin_api_version} "
                    f"does not match app's PLUGIN_API_VERSION={PLUGIN_API_VERSION}. Skipped.",
                )
            )
            continue
        order = cls.plugin_order
        if not isinstance(order, (int, float)) or isinstance(order, bool):
            errors.append(
                StageLoadError(
                    cls.__module__,
                    f"{cls.__name__}: plugin_order must be a number, got {order!r}. Skipped.",
                )
            )
            continue
        try:
            instances.append(cls())
        except Exception as exc:
            errors.append(StageLoadError(cls.__module__, f"{cls.__name__}: {exc}"))
    instances.sort(key=lambda stage: stage.plugin_order)
    return instances, errors


def load_all_stages(
    plugins_dir: Path,
) -> tuple[list[StageWidgetBase], list[StageWidgetBase], list[StageLoadError]]:
    """組み込みステージと外部プラグインを別々に検出・インスタンス化する。

    組み込みステージは常時表示の固定タブ、プラグインは「Plugins」ボタン経由で
    選択的に表示するタブとして main_window 側で扱われるため、呼び出し元で
    区別できるよう別のリストとして返す。
    """
    builtin_classes, builtin_errors = discover_builtin_stage_classes()
    plugin_classes, plugin_errors = discover_plugin_stage_classes(plugins_dir)
    builtin_instances, builtin_instantiate_errors = instantiate_stages(builtin_classes)
    plugin_instances, plugin_instantiate_errors = instantiate_stages(plugin_classes)
    errors = builtin_errors + plugin_errors + builtin_instantiate_errors + plugin_instantiate_errors
    return builtin_instances, plugin_instances, errors
