"""QSettingsを使った永続設定(sam2環境ルート・直近使用ディレクトリ等)。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings

ORG_NAME = "KymoTip"
APP_NAME = "KymoTip_GUI"


def _default_sam2_root() -> str:
    """パッケージ版(PyInstaller)で、同梱のsam2環境が実際に存在する場合のみその
    絶対パスを返す。ソースから実行中(開発時)は何も返さず、ユーザーが従来通り
    フォルダ選択で指定する(開発機ではFiji同梱環境等を使うため)。
    """
    if not getattr(sys, "frozen", False):
        return ""
    bundled = Path(sys.executable).resolve().parent / "sam2env"
    return str(bundled) if bundled.is_dir() else ""


def _is_valid_sam2_root(path: str) -> bool:
    """保存済みsam2_rootに実際にpython実行ファイルが存在するか確認する。
    再インストールやインストール先変更で古い絶対パスが残った場合に、
    存在しないパスをそのまま使い続けてしまうのを防ぐ。
    """
    root = Path(path)
    exe = root / "python.exe" if sys.platform == "win32" else root / "bin" / "python3"
    return exe.is_file()


class AppSettings:
    def __init__(self) -> None:
        self._settings = QSettings(ORG_NAME, APP_NAME)

    @property
    def sam2_root(self) -> str:
        saved = self._settings.value("sam2_root", "", str)
        if saved and _is_valid_sam2_root(saved):
            return saved
        return _default_sam2_root()

    @sam2_root.setter
    def sam2_root(self, value: str) -> None:
        self._settings.setValue("sam2_root", value)

    @property
    def device_preference(self) -> str:
        return self._settings.value("device_preference", "auto", str)

    @device_preference.setter
    def device_preference(self, value: str) -> None:
        self._settings.setValue("device_preference", value)

    @property
    def project_base_dir(self) -> str:
        return self._settings.value("project_base_dir", "", str)

    @project_base_dir.setter
    def project_base_dir(self, value: str) -> None:
        self._settings.setValue("project_base_dir", value)

    @property
    def project_fname(self) -> str:
        return self._settings.value("project_fname", "", str)

    @project_fname.setter
    def project_fname(self, value: str) -> None:
        self._settings.setValue("project_fname", value)

    def last_dir(self, key: str) -> str:
        return self._settings.value(f"last_dir/{key}", "", str)

    def set_last_dir(self, key: str, value: str) -> None:
        self._settings.setValue(f"last_dir/{key}", value)
