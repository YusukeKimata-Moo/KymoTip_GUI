import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path(SPECPATH).parent
# kymotipはpip installされていないソース直下パッケージのため、collect_submodulesが
# Analysis()より前に評価される時点でimportできるよう、先にsys.pathへ入れる。
# 入れ忘れると例外もwarningも出ず空リストになり、パッケージ版でタブが消える
# (詳細はkymotip-windows.specのコメントを参照)。
sys.path.insert(0, str(project_root))
app_icon = project_root / "packaging" / "icons" / "kymotip.icns"
runtime_icon = project_root / "packaging" / "icons" / "kymotip.png"
sam2_worker = project_root / "kymotip" / "segmentation" / "sam2_worker.py"
app_version = os.environ.get("KYMOTIP_VERSION", "0.0.0-dev")

a = Analysis(
    [str(project_root / "packaging" / "launcher.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(runtime_icon), "packaging/icons"),
        (str(sam2_worker), "kymotip/segmentation"),
    ],
    hiddenimports=(
        collect_submodules("kymotip.gui.stages")
        # plugins/はビルド解析対象外(実行時に動的ロードされる)ため、プラグインが
        # 使いうるサブモジュールを丸ごと同梱する(Windows版と同じ方針)。
        + collect_submodules("scipy")
        + collect_submodules("skimage")
        + collect_submodules("matplotlib")
        + collect_submodules("loess")
    ),
    hookspath=[],
    # matplotlibは既定で全バックエンドを収集しようとするため、実際に使うQtのみに限定する。
    hooksconfig={"matplotlib": {"backends": ["qtagg"]}},
    runtime_hooks=[],
    excludes=[
        # SAM2/torchは別環境(sam2env)からsubprocessで呼ぶ設計のため凍結対象外。
        "torch",
        "sam2",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "pytest",
        "_pytest",
    ],
    noarchive=False,
)

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
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="KymoTip",
)

# sam2envはここでは含めない。.app作成後にCIが<app>/Contents/Resources/sam2envへ
# コピーし、全体をad-hoc署名する(packaging/README.mdのmacOS節を参照)。
app = BUNDLE(
    coll,
    name="KymoTip.app",
    icon=str(app_icon),
    bundle_identifier="com.kymotip.KymoTip",
    version=app_version,
    info_plist={
        "CFBundleName": "KymoTip",
        "CFBundleDisplayName": "KymoTip",
        "CFBundleShortVersionString": app_version,
        "NSHighResolutionCapable": True,
    },
)
