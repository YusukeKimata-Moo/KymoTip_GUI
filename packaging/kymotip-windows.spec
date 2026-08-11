from pathlib import Path

import PySide6
from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).parent
app_icon = project_root / "packaging" / "icons" / "kymotip.ico"
runtime_icon = project_root / "packaging" / "icons" / "kymotip.png"
sam2_worker = project_root / "kymotip" / "segmentation" / "sam2_worker.py"

a = Analysis(
    [str(project_root / "packaging" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(runtime_icon), "packaging/icons"),
        (str(sam2_worker), "kymotip/segmentation"),
    ],
    hiddenimports=collect_submodules("kymotip.gui.stages"),
    hookspath=[],
    # matplotlibは既定で全バックエンド(Tk/GTK/nbAgg等)を収集しようとし、
    # nbAgg経由でIPython/Jupyter一式まで巻き込んでビルドが肥大化するため、
    # 実際に使うQtバックエンドのみに限定する。
    hooksconfig={"matplotlib": {"backends": ["qtagg"]}},
    runtime_hooks=[],
    excludes=[
        "torch",
        "sam2",
        "PyQt5",
        "PyQt6",
        "PySide2",
        # kymotip本体が直接使わない、Anaconda環境由来の巨大な無関係パッケージ。
        # 同梱すると配布サイズが肥大化するだけでなく、これらが持つ独自の
        # VCRUNTIME140.dll/MSVCP140.dll等が先に読み込まれ、後からロードする
        # Qt6*.dllとバージョンが食い違ってDLLロードエラー(error 127)を
        # 引き起こすため除外する。
        "pandas",
        "pyarrow",
        "IPython",
        "ipykernel",
        "jupyter",
        "jupyter_client",
        "jupyter_core",
        "jupyter_server",
        "jupyterlab",
        "jupyterlab_server",
        "notebook",
        "nbclassic",
        "ipywidgets",
        "widgetsnbextension",
        "nbformat",
        "jsonschema",
        "jsonschema_specifications",
        "zmq",
        "jedi",
        "parso",
        "pytest",
        "_pytest",
        "sphinx",
        "sphinxcontrib",
        "docutils",
        "black",
        "blib2to3",
        "yapf_third_party",
        "numba",
        "llvmlite",
        "tables",
        "h5py",
        "grpc",
        "paramiko",
        "bcrypt",
        "nacl",
    ],
    noarchive=False,
)

# このAnaconda環境ではPyInstallerのQtプラグイン自動収集フック
# (hook-PySide6.QtGui.py -> add_qt6_dependencies -> pyside6_library_info)が
# 内部で`import PySide6.QtCore`を素の状態(_qt_bootstrap.pyのDLL事前ロードなし)の
# 別プロセスで試みるため失敗し、platforms/qwindows.dll等が一切同梱されず
# 「no Qt platform plugin could be initialized」で起動不能になる。
# 実行時ランタイムフックpyi_rth_pyside6.pyがQT_PLUGIN_PATHを
# `<_MEIPASS>/PySide6/plugins`に無条件で設定するため、そこに手動で
# プラグインDLLを配置すれば自動収集の失敗を回避できる。
_qt_plugins_src = Path(PySide6.__file__).resolve().parent / "plugins"
_QT_PLUGIN_CATEGORIES = ("platforms", "styles", "imageformats")
for _category in _QT_PLUGIN_CATEGORIES:
    for _dll in (_qt_plugins_src / _category).glob("*.dll"):
        a.binaries.append(
            (f"PySide6/plugins/{_category}/{_dll.name}", str(_dll), "BINARY")
        )

# numpy/scipy/opencv等が別バージョンのVCRUNTIME140.dll/MSVCP140.dllを
# 同梱し、_internal直下(pythonXXX.dllと同じ場所)にそれが配置されると、
# プロセス起動時にそちらが先にロードされてしまう。Windowsは同名DLLを
# プロセス内で1つしかロードしないため、後からPySide6/Qt6*.dllが必要と
# するVCRUNTIME/MSVCPを探しても、既にロード済みの(互換性のない)方が
# 再利用され、DLLロードエラー(error 127: procedure not found)になる。
# そのためルート直下に配置される分もPySide6同梱版で上書きし、プロセス内で
# 常に単一の一貫したバージョンだけが使われるようにする。
_RUNTIME_DLL_NAMES = {
    "VCRUNTIME140.dll",
    "VCRUNTIME140_1.dll",
    "MSVCP140.dll",
    "MSVCP140_1.dll",
    "MSVCP140_2.dll",
}
_pyside6_runtime_src = {
    Path(dest).name: src
    for dest, src, _typecode in a.binaries
    if Path(dest).name in _RUNTIME_DLL_NAMES and Path(dest).parent.name == "PySide6"
}
for _i, (_dest, _src, _typecode) in enumerate(a.binaries):
    _name = Path(_dest).name
    if _name in _pyside6_runtime_src and Path(_dest).parent.name != "PySide6":
        a.binaries[_i] = (_dest, _pyside6_runtime_src[_name], _typecode)

# opencv/numpy等の依存解析で自動的に同梱されるicuuc.dll/icudtXX.dllは、
# Anaconda(conda-forge)のICUビルド(シンボル名に"_73"等のバージョン
# サフィックスが付くリネームビルド)であり、PySide6のQt6Core.dllが要求する
# 無印シンボル名(例: ucnv_open)とABI非互換で、同梱するとDLLロードエラー
# (error 127: procedure not found)になる。Windowsは10以降、この無印
# シンボルで動作する互換icuuc.dllをSystem32に標準搭載しているため、
# 自前で同梱せずOS標準のものに解決を任せる。
_ICU_DLL_PATTERN = ("icuuc", "icudt", "icuin", "icuio", "icutu")
a.binaries = [
    (_dest, _src, _typecode)
    for _dest, _src, _typecode in a.binaries
    if not Path(_dest).name.lower().startswith(_ICU_DLL_PATTERN)
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="KymoTip",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(app_icon),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="KymoTip",
)
