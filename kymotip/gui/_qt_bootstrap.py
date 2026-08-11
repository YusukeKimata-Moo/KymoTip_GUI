"""PySide6インポート前のWindows DLL解決ワークアラウンド。

このAnaconda環境ではPATH上の別パッケージ由来のDLLが優先されてしまい、
PySide6同梱のQt6*.dllが依存DLLを正しく解決できずImportError
(WinError 127)になる。PySide6自身のフォルダを検索基点として明示的に
Qt6Core/Gui/Widgetsを事前ロードしておくことで、後続の
`from PySide6.QtWidgets import ...` 等がロード済みDLLを再利用し回避できる。
"""
from __future__ import annotations

import ctypes
import os
import sys

_LOAD_WITH_ALTERED_SEARCH_PATH = 0x08
_PRELOAD_DLLS = ("Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll")

_done = False


def ensure_qt_dlls_loaded() -> None:
    global _done
    if _done or sys.platform != "win32":
        return
    _done = True

    import PySide6

    package_dir = os.path.dirname(PySide6.__file__)
    kernel32 = ctypes.windll.kernel32
    kernel32.LoadLibraryExW.restype = ctypes.c_void_p
    kernel32.LoadLibraryExW.argtypes = [ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_uint32]

    for name in _PRELOAD_DLLS:
        path = os.path.join(package_dir, name)
        if not os.path.exists(path):
            continue
        handle = kernel32.LoadLibraryExW(path, None, _LOAD_WITH_ALTERED_SEARCH_PATH)
        if not handle:
            error_code = kernel32.GetLastError()
            print(
                f"[kymotip.gui] Qt DLL事前ロードに失敗しました: {name} (error {error_code})",
                file=sys.stderr,
            )
