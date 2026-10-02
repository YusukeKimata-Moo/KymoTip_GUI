# KymoTip packaging

The Windows package uses separate icons by context:

- `icons/kymotip.ico`: executable, taskbar, and Qt window icon (Core Trace without text)
- `icons/kymotip-shortcut.ico`: desktop and Start menu shortcuts (Center Knockout with wordmark)

## Windows build

Run these commands from the repository root with the project Anaconda environment activated:

```powershell
python packaging\icons\build_icons.py
python packaging\icons\build_square_logos.py
python -m PyInstaller --clean --noconfirm packaging\kymotip-windows.spec
```

Compile the installer with Inno Setup after replacing the development version:

```powershell
& "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=1.0.0 packaging\windows\KymoTip.iss
```

The result is written below `dist/installer/`. The installer uses the Center Knockout icon for its desktop and Start menu shortcuts while the installed executable and running GUI retain the mark-only icon.

## macOS build (untested)

The macOS package (Apple Silicon only) is built by the GitHub Actions workflow `.github/workflows/build-macos.yml` on a `macos-14` runner; it has never been run on a real Mac. Trigger it from the Actions tab (workflow_dispatch) or by pushing a `v*` tag. The bundled `tiny` checkpoint is downloaded during the build.

The workflow runs these steps, which can also be run by hand on a Mac:

```bash
bash packaging/macos/build_sam2_env.sh /tmp/sam2env
KYMOTIP_VERSION=1.0.2 python -m PyInstaller --clean --noconfirm packaging/kymotip-macos.spec
ditto /tmp/sam2env dist/KymoTip.app/Contents/Resources/sam2env
codesign --force --deep --sign - dist/KymoTip.app
```

`build_sam2_env.sh` builds the SAM2 environment from a relocatable Python (python-build-standalone via `uv`) with the same torch/torchvision/samv2 versions as the Windows bundle. The app finds it at `Contents/Resources/sam2env`. The resulting `.dmg` is uploaded as a workflow artifact and must be attached to a GitHub Release manually.
