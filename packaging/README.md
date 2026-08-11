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
