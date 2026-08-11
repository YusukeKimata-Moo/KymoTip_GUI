# KymoTip application icons

`kymotip.*` is the adopted **Core Trace** design.

- `kymotip.ico`: Windows executable, taskbar, and GUI icon. Contains 16, 24, 32, 48, 64, 128, and 256 px images.
- `kymotip.icns`: macOS application bundle icon.
- `kymotip.png`: 1024 px PNG for Linux, documentation, and runtime GUI use.
- `kymotip-shortcut.ico`: Center Knockout wordmark for Windows desktop and Start menu shortcuts.
- `kymotip-shortcut.png`: 1024 px source for the shortcut icon.
- `concepts/kymotip-core-trace-source.png`: original generated source for rebuilding the mark-only icon.

PyInstaller should use the mark-only platform icon:

```text
Windows: --icon packaging/icons/kymotip.ico
macOS:   --icon packaging/icons/kymotip.icns
```

Windows installer builders such as Inno Setup should install `kymotip-shortcut.ico` and assign it only to desktop and Start menu shortcuts. Rebuild the derived files with the project Anaconda environment activated:

```powershell
python packaging\icons\build_icons.py
python packaging\icons\build_square_logos.py
```
