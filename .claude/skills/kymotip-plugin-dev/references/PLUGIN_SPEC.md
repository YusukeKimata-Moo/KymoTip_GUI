# KymoTip Plugin Specification

KymoTip is a desktop GUI for quantifying cell tip growth dynamics from
time-lapse microscopy images. Its analysis pipeline is a fixed sequence of
stages (00_raw → 07_growth); in addition to those, users can add their own
custom quantification (cell shape, distribution of internal structures,
etc.) as a "plugin". This document describes how to write a plugin and the
rules for sharing a finished plugin with the rest of the lab.

This file, together with
`../assets/plugin_examples/cell_shape_example_plugin/`, is written so that a
coding agent such as Claude Code can be handed plugin development directly after
reading them.

## 0. Background: projects, stages, and frames

A KymoTip **project** is a `base_dir` folder plus a `fname` (file name
prefix) shared by all the frame files in that project. Frame files are named
`"{fname}_{frame:03d}.{ext}"` (e.g. `sample_001.tif`). Every built-in
pipeline stage reads frames from one fixed subfolder of `base_dir` and
writes its output to another (see section 3 for the fixed subfolder names).

The **"Input Preview"** tab (step 0) is where the user sets `base_dir` and
`fname` for a project. Its **"Apply to All Stages"** button propagates that
`base_dir`/`fname` to every stage — including plugins — by calling each
stage's `wire_project(base_dir, fname)`. A stage/plugin that does not
implement `wire_project` simply keeps whatever input/output directories the
user has set manually.

A **stage** (built-in or plugin) is one GUI tab: it has input/output
directory pickers, a "Run" button, a progress bar, a log view, and a preview
pane, and it runs one processing step over the frames in its input directory.
`StageWidgetBase` (section 2) provides all of this scaffolding.

## 1. Quick start

1. Prepare a `plugins/` folder (KymoTip creates it automatically on startup
   if it doesn't exist). Its location depends on how KymoTip is run — see
   section 5 for details:
   - Running from source: `plugins/` at the repository root (already
     `.gitignore`d, so feel free to use it freely).
   - Packaged KymoTip (installer build): the OS-specific user data
     directory (on Windows, `%LOCALAPPDATA%\KymoTip\plugins`).
2. Copy the whole `../assets/plugin_examples/cell_shape_example_plugin/`
   folder into `plugins/`, then rename the folder and rewrite the class name and logic
   in `__init__.py`.
3. Restart the KymoTip GUI. The new plugin appears in the toolbar's
   "Plugins" menu. Checking it opens a tab; unchecking it (or closing the
   tab with its × button) closes it again. Unlike the built-in stages
   (0–7), plugin tabs are not shown permanently.

## 2. Contract a plugin must satisfy

A plugin is **one folder per plugin** (a single file is not supported).
Place `plugins/my_plugin/__init__.py`, and optionally add helper modules
(e.g. `helper.py`) or a `README.md` in the same folder. `__init__.py` can
use relative imports such as `from .helper import compute_area`. This
mirrors Claude Code's agent skill format (`SKILL.md` plus supporting files
in one folder), so a plugin can be distributed and shared simply by copying
its folder. Folders without an `__init__.py`, or whose name starts with
`_`, are not recognized as plugins.

Inside `__init__.py` itself, or in a helper module reached via a relative
import, define **one or more** subclasses of `StageWidgetBase` satisfying:

```python
from kymotip.plugin_api import StageWidgetBase

class MyStage(StageWidgetBase):
    stage_title = "My Measurement"     # required; also used as the group-box heading inside the tab
    tab_label = "My Measurement"       # optional; set only if you want a shorter name in the tab/Plugins menu
    plugin_order = 2.5                 # required; if left as None, the plugin won't appear in the "Plugins" menu
    plugin_api_version = 1             # optional (defaults to 1); if it doesn't match
                                        # kymotip.plugin_api.PLUGIN_API_VERSION, loading is skipped

    def wire_project(self, base_dir, fname):
        ...  # auto-set this stage's input/output directories when "Apply to All Stages" runs (optional)

    def build_parameter_form(self, form_layout):
        ...  # add parameter input fields

    def build_task(self):
        ...  # return a zero-argument callable; it runs on a background thread

    def on_task_finished(self, result):
        ...  # receives the return value of build_task() to update the preview, etc. (optional)
```

- `plugin_order` controls the ordering of plugins relative to each other
  within the "Plugins" menu (it has no effect on the built-in stages' tab
  numbers; plugin tabs are shown without a number). It doesn't need to avoid
  colliding with the existing stages (1–7); an in-between value such as
  `2.5` is a common convention.
- If `wire_project` is not implemented, a no-op default is used (pressing
  "Apply to All Stages" in Input Preview will not change this stage's
  input/output fields).

`StageWidgetBase` automatically provides `input_dir_picker` /
`output_dir_picker` / `run_button` / `progress_bar` / `log_view` /
`preview`, etc. Their exact behavior can be found in
`kymotip/gui/stages/base.py`, but plugins must not import
`kymotip.gui.stages.base` directly (see section 4).

## 3. Directory naming convention

Across the whole pipeline, everything under a project's `base_dir` uses the
following fixed names. Follow this convention if you implement
`wire_project`.

```
00_raw / 01_registration / 02_segmentation / 03_contour /
04_trajectory / 05_centerline / 06_kymograph / 07_growth
```

Frame file names follow `"{fname}_{frame:03d}.{ext}"`. To consume the
output of an existing stage as input, just read from the matching existing
directory (e.g. `02_segmentation`). For your plugin's own output, pick a
name that doesn't collide with the list above (e.g.
`base_dir / "cell_shape_example"`) and create it with `ensure_dir()`.

## 4. Allowed API (kymotip.plugin_api)

Plugins **must not** import `kymotip.core.*` / `kymotip.gui.*` internal
modules directly — internal implementation details may change in future
refactors. Always go through `kymotip.plugin_api`. Currently exported names:

```python
from kymotip.plugin_api import (
    PLUGIN_API_VERSION,
    StageWidgetBase,
    DirPicker,
    append_log,
    discover_frames,
    ensure_dir,
    frame_filename,
    frame_path,
    normalize_for_display,
    read_image_any,
    read_reference_image_size,
    save_xy_plot,
    write_image_any,
)
```

For image/numeric processing itself, ordinary third-party libraries such as
`numpy`, `PIL`, and `PySide6.QtWidgets` may be used directly. The only thing
that's prohibited is depending directly on `kymotip.core.*` /
`kymotip.gui.*` internal modules.

However, since KymoTip itself ships as a packaged installer, the
third-party libraries a plugin can rely on are **limited to what the
installer already bundles** (numpy, PIL, PySide6, etc.). You cannot assume
end users can freely `pip install` anything, so if a plugin needs a library
that isn't bundled, discuss it beforehand.

If an unbundled library is truly needed, how to handle it depends on the
kind of library:

- **Pure-Python libraries** (no C extensions, works as plain `.py` files):
  it's fine to vendor them inside the plugin folder and import them with a
  relative import. Example: place it at
  `plugins/my_plugin/vendor/somelib/` and import with
  `from .vendor import somelib`. No change to the installer is needed.
- **Compiled/binary libraries** (things like numpy or scipy that include
  C/C++ extensions): the vendoring approach above doesn't work (the binary
  differs per OS/Python version). It needs to be bundled by the maintainers
  the next time the installer is built.
- **Runtime `pip install`**: the packaged environment isn't guaranteed to
  have write permissions, `pip` itself, or even a network connection —
  don't rely on this working.

## 5. Loading and fault isolation

At startup, KymoTip automatically scans:

1. Built-in stages: each module under `kymotip/gui/stages/`
2. User plugins: each folder with an `__init__.py` under `plugins/`
   (the location of `plugins/` is the repository root when running from
   source, and the user data directory when running as a packaged
   executable — see section 1)

In both cases, a failure to load (import/instantiate) a single
module/class does not stop the whole app — only the failed one is skipped
and the rest continue (`kymotip/gui/plugin_loader.py`). If any stage/plugin
fails to load, a warning dialog summarizing the failures is shown at
startup. Runtime errors from `build_task()` are shown in that tab's log
panel and an error dialog, just like a built-in stage. Exceptions raised
from `wire_project()` are recorded in that stage's log panel, and
`wire_project()` calls for the other stages continue regardless.

A plugin whose `plugin_api_version` doesn't match
`kymotip.plugin_api.PLUGIN_API_VERSION` is skipped as a warning rather than
an error (this protects against a breaking API change in a future KymoTip
version).

A successfully loaded plugin is not opened as a tab yet at this point —
only instantiation happens at startup. Whether it's actually shown as a tab
is chosen by the user from the toolbar's "Plugins" menu. This keeps adding
more plugins from reordering the built-in stages' tabs or from making the
tab bar grow without bound.

## 6. Sharing within the lab

KymoTip itself is distributed as a packaged installer, and end users don't
have the repository. So sharing a plugin isn't "merge it into the
repository" — it means **copying the plugin folder itself and handing it
over**.

- **Personal use**: the installed `plugins/` folder can be freely
  experimented with on each person's own PC; no review is needed.
- **Sharing**: a plugin judged useful to other lab members is distributed
  by copying the whole folder (via a shared drive, Slack, a USB stick,
  whatever works). The recipient just drops that folder into their own
  `plugins/` to use it. Before distributing, check that it satisfies this
  document's contract (sections 2–4) rather than being left as personal,
  throwaway code. Including a `README.md` inside the folder lets the
  recipient understand how to use it without reading the code (the same
  idea as distributing an agent's skill folder).
- A plugin the maintainers judge especially useful can also be considered
  for bundling into a future installer release by default (following the
  normal release process in that case).

## 7. Example

`../assets/plugin_examples/cell_shape_example_plugin/` is a minimal example that
computes per-frame area and perimeter from `02_segmentation` mask images and
writes them out as a tab-separated log. It consists of two files:
`__init__.py` (the implementation) and `README.md` (usage notes). Use it as
a template for new plugins by copying the whole folder.
