<p align="center">
  <img src="packaging/icons/kymotip-shortcut.png" alt="KymoTip logo" width="320">
</p>

<h1 align="center">KymoTip</h1>

<p align="center">
  A desktop GUI for easily quantifying cell tip growth dynamics.
</p>

## Overview

KymoTip is a desktop application for quantifying cell tip growth dynamics
from time-lapse microscopy images. It packages a full analysis pipeline —
registration, SAM2-based segmentation, contour extraction, trajectory
smoothing, centerline extraction, kymograph rendering, and growth-rate
plotting — into a single GUI, so no manual Python environment setup is
required.

## User Manual

For detailed usage instructions, see the user manual:

- [English](docs/user_manual_en.md)
- [日本語](docs/user_manual_ja.md)

## Installation

### Windows

1. Download the latest `KymoTip-<version>-Setup.exe` from the
   [Releases](../../releases) page.
2. Run the installer. No administrator privileges are required; it installs
   to your user-local application folder.
3. Launch KymoTip from the Start menu or desktop shortcut.

The installer bundles everything needed to run, including a dedicated Python
environment for SAM2 segmentation. A one-time download of the SAM2 model
checkpoint occurs automatically the first time you use a checkpoint other
than the bundled `tiny` model; an internet connection is required for that.

> **Note:** The installer is not code-signed. On first launch, Windows
> SmartScreen may show a warning. Click **More info → Run anyway** to
> proceed.

### macOS

Not currently supported.

### Building from source

KymoTip can also be built from source instead of using the prebuilt
installer. See [`packaging/README.md`](packaging/README.md) for build
instructions.

## Plugin development

Beyond the built-in pipeline stages, KymoTip supports user-written plugins
that add a custom measurement tab (e.g. cell shape, distribution of internal
structures). Plugins are self-contained folders dropped into a `plugins/`
directory — no rebuild of KymoTip required. If you use
[Claude Code](https://claude.com/product/claude-code), this repository
bundles a skill at
[`.claude/skills/kymotip-plugin-dev`](.claude/skills/kymotip-plugin-dev)
that guides an agent through writing one, including the full specification
and a working example plugin. The Windows installer copies this skill
folder into the installed application folder as `.claude/`, so it's
available for plugin development even if you only installed the prebuilt
app and didn't clone this repository.
`gaussian_fit_detection` (object position/width detection via 1D Gaussian
fitting) is a real-world example plugin, available as a zip archive on the
[GitHub Releases](../../releases) page.

## Requirements

- Windows 10/11 (64-bit)
- Internet connection (only needed if you select a SAM2 checkpoint other
  than `tiny`)

## Reference

If you use this tool in your research, please cite the following paper:

> Kang, Z., Kimata, Y., Nonoyama, T., Ikeuchi, T., Kuchitsu, K., Tsugawa, S. and Ueda, M. (2026), KymoTip: high-throughput characterization of tip-growth dynamics in plant cells. _Plant J_, 125: e70691. https://doi.org/10.1111/tpj.70691

## License

KymoTip is released under the [MIT License](LICENSE).

KymoTip bundles [PySide6](https://pypi.org/project/PySide6/) (Qt for
Python), which is licensed under the GNU Lesser General Public License v3
(LGPLv3). The Qt/PySide6 components are distributed as separate,
independently replaceable files rather than statically linked into the
application.

- LGPLv3 full text: https://www.gnu.org/licenses/lgpl-3.0.txt
- Qt/PySide6 source: https://code.qt.io/ , https://pypi.org/project/PySide6/

KymoTip also bundles [SAM2](https://github.com/facebookresearch/sam2)
(Meta Platforms, Inc., installed via the
[`samv2`](https://github.com/SauravMaheshkar/samv2) PyPI package), licensed
under the Apache License 2.0. Model checkpoints are licensed under the same
terms.
