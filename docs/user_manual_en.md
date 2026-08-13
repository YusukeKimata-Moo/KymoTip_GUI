# KymoTip User Manual

## Contents

1. [Introduction](#1-introduction)
2. [Installation and Launch](#2-installation-and-launch)
3. [Quick Start](#3-quick-start)
4. [Interface Basics](#4-interface-basics)
5. [Input File Format and Naming](#5-input-file-format-and-naming)
6. [Stage Reference](#6-stage-reference)
7. [Plugins](#7-plugins)
8. [FAQ and Troubleshooting](#8-faq-and-troubleshooting)
9. [Appendix](#9-appendix)

---

## 1. Introduction

KymoTip is a desktop application for quantifying cell tip growth dynamics from time-lapse microscopy images. It packages the entire analysis pipeline into a single GUI: registration, SAM2-based segmentation, contour extraction, trajectory smoothing, centerline extraction, kymograph rendering, and growth-rate plotting, with no separate Python environment to set up.

The window is organized as a row of tabs, numbered "0. Input Preview" through "7. Growth," meant to be worked through left to right. Each stage's output folder feeds directly into the next stage's input folder, so running the tabs in order is generally all it takes to complete the pipeline.

This manual is written for researchers measuring tip growth rates from time-lapse microscopy data. No programming background is assumed.

---

## 2. Installation and Launch

### Windows

1. Download the latest `KymoTip-<version>-Setup.exe` from the [Releases](../../releases) page.
2. Run the installer. No administrator privileges are required; it installs into your user-local application folder.
3. Launch KymoTip from the Start menu or the desktop shortcut.

The installer bundles everything the app needs to run, including a dedicated Python environment for SAM2 segmentation. The first time you select a SAM2 checkpoint other than `tiny`, its model file is downloaded automatically; that's the only situation where an internet connection is required.

> **Note:** The installer isn't code-signed, so Windows SmartScreen may show a warning on first launch. Click **More info → Run anyway** to proceed.

### macOS

Not currently supported.

### System Requirements

- Windows 10/11 (64-bit)
- Internet connection (only needed when selecting a SAM2 checkpoint other than `tiny`)

---

## 3. Quick Start

If this is your first time using KymoTip, the fastest way to get oriented is to run a single sample dataset through all eight tabs, start to finish. Seeing the whole pipeline once makes it much easier to understand what each stage is actually doing.

1. **Prepare your images.** Put a time-lapse image series in one folder, named according to the pattern `{prefix}_{3-digit frame number}.{extension}` (e.g. `sample_000.tif`; see [5. Input File Format and Naming](#5-input-file-format-and-naming) for details). Naming the folder `00_raw` lets you take advantage of the bulk-apply feature described below.
2. **Open the "0. Input Preview" tab.** Point "Input directory" at that image folder and click "Load frames" to confirm the frames read correctly.
3. **Apply the project settings.** In the same tab, set "Project base directory" to the parent folder that contains `00_raw`, enter the shared part of the file name under "File name prefix," and click "Apply to All Stages." This fills in the input/output folders and file name prefix for every downstream stage automatically.
4. **Run "1. Registration."** The default parameters are fine to start with. Click "Run" to align the frames, and check the result in the preview panel on the right.
5. **Mark your target in "2. Segmentation."** Click "Load Frames from Input Directory," then "Add Object" to create one tracking target (e.g. a cell), and click on the preview image: left-click to mark the region you want included, right-click to mark anything that should be excluded. Clicking "Run" propagates a mask across every frame based on those points.
6. **Run "3. Contour" through "5. Centerline" in order.** Each of these can simply be run with default parameters; together they extract the outline, smooth it, and derive the centerline. Check the preview after each run to make sure the shape looks reasonable.
7. **Generate a kymograph in "6. Kymograph."** Confirm the mask folder, centerline folder, and object ID (defaults to `obj0`), then click "Run" to produce the kymograph image.
8. **Compute growth rate in "7. Growth."** Enter "Pixels per micron" and "Time interval" to match your imaging conditions, then click "Run" to get cell-length and growth-rate plots plus a CSV summary.

Once you have a feel for the overall flow, use [6. Stage Reference](#6-stage-reference) to understand each parameter in more depth as you tune the pipeline for your own data.

---

## 4. Interface Basics

Every processing-stage tab shares the same layout: a control panel on the left, a preview on the right.

- **Input directory / Output directory**: take a path you can type directly or choose with the "Browse..." button.
- **Parameter fields**: specific to that stage. Stages with a lot of parameters scroll vertically so everything stays reachable.
- **Run button**: starts processing. It runs in a background thread, so the interface stays responsive while it works.
- **Progress bar**: appears while a run is in progress and disappears once it finishes.
- **Log panel**: records start and finish messages plus any errors in order. If something goes wrong, that's the first place to check.

The preview on the right shows either an image you can step through frame by frame or a plot of the contour, centerline, or resulting graph, depending on the stage. It refreshes automatically once a run finishes.

### Applying project settings to every stage at once

The "0. Input Preview" tab has a couple of controls that don't appear anywhere else:

- **Project base directory / File name prefix**: the shared base folder and file name prefix for the whole project.
- **Apply to All Stages**: click this to fill in the Input directory, Output directory, and File name prefix for every stage from "1. Registration" through "7. Growth," following this mapping:

| Stage | Input directory | Output directory |
|---|---|---|
| 1. Registration | `{base}/00_raw` | `{base}/01_registration` |
| 2. Segmentation | `{base}/01_registration` | `{base}/02_segmentation` |
| 3. Contour | `{base}/02_segmentation` | `{base}/03_contour` |
| 4. Trajectory | `{base}/03_contour` | `{base}/04_trajectory` |
| 5. Centerline | `{base}/04_trajectory` | `{base}/05_centerline` |
| 6. Kymograph | images: `{base}/01_registration`, masks: `{base}/02_segmentation`, centerline: `{base}/05_centerline` | `{base}/06_kymograph` |
| 7. Growth | `{base}/05_centerline` | `{base}/07_growth` |

This saves you from setting every folder by hand. When you switch to a different project (a different image set), just change the project base directory and file name prefix and click "Apply to All Stages" again.

### The "Auto-detect from input directory" button

Most stages include a button that scans the Input directory and fills in "File name prefix" and "Number of frames" automatically. As long as the files in that folder follow the naming convention described in [5. Input File Format and Naming](#5-input-file-format-and-naming), this one click saves you from typing those values in by hand.

---

## 5. Input File Format and Naming

KymoTip's pipeline recognizes image files in a folder using this naming pattern:

```
{file name prefix}_{frame number, zero-padded to 3 digits}.{extension}
```

For example: `sample_000.tif`, `sample_001.tif`, `sample_002.tif`, …

- Frame numbers should start at `000` and increase consecutively. The frame count is inferred as the highest frame number found in the folder, plus one, so a gap in the sequence will throw off the detected count.
- Common grayscale image formats are supported, including TIFF and PNG. Both 8-bit and 16-bit images work; 16-bit pixel values are preserved at full precision throughout the pipeline rather than being truncated to 8-bit.
- When loading frames on the Segmentation tab specifically, only files with a `.png`, `.tif`, or `.tiff` extension are picked up.
- If a folder contains files with more than one prefix or extension, "Auto-detect from input directory" picks whichever combination appears most often. If it detects the wrong prefix, either move the unrelated files out of the folder or type the correct prefix in by hand.

### How the folder structure works

When you use "Apply to All Stages," a set of numbered subfolders is built up under your project's base folder as you work through the pipeline: `00_raw`, `01_registration`, `02_segmentation`, `03_contour`, `04_trajectory`, `05_centerline`, `06_kymograph`, `07_growth`. You only need to prepare the raw images in `00_raw` yourself; every later folder is created automatically as each stage runs.

---

## 6. Stage Reference

### 0. Input Preview

A tab for checking your input frames before running anything else.

- **Project base directory / File name prefix / Apply to All Stages**: see [4. Interface Basics](#4-interface-basics).
- **Input directory / Load frames**: independent of the project-wide settings above, this lets you browse any folder's frames on the spot. Clicking "Load frames" reports the detected file name prefix, extension, and frame count, and lets you step through the frames in the preview.

### 1. Registration

Corrects frame-to-frame drift and rotation introduced during time-lapse acquisition.

| Field | Description |
|---|---|
| File name prefix (reference channel) | The channel used as the reference for computing alignment |
| Number of channels | 1 to 3. Channels 2 and 3 simply reuse the shift and rotation computed from the reference channel, so you only need to give each one its own input/output folder and file name prefix (candidates ending in `_ch2` / `_ch3` are filled in automatically, but can be edited) |
| Start angle / End angle / Angle step (deg) | The range and step size used when searching for the best alignment angle |
| Start frame / Number of frames | Which frames to process |
| Reference refresh interval (d) | How often the reference frame is refreshed (leave at 0 to keep using the first frame throughout) |
| Noise fill range (n_fill) | The brightness range used to fill in blank borders left by translation/rotation |
| Preview channel | Which channel to display in the preview after a run |

Output: aligned frames, written to the output folder using the same naming convention as the input.

### 2. Segmentation (SAM2)

Uses SAM2 (Segment Anything Model 2) to automatically track and segment a target region, a cell, for example, across every frame, based on points you click on a reference frame.

| Field | Description |
|---|---|
| SAM2 environment root | The folder containing the SAM2 Python environment. The installed version of KymoTip fills this in automatically with its bundled environment |
| Checkpoint | `tiny`, `small`, `base_plus`, or `large`. Larger models are more accurate but slower. Anything other than `tiny` is downloaded automatically the first time it's used (requires an internet connection) |
| Load Frames from Input Directory | Loads PNG/TIFF frames from the input directory |
| Reference frame | The frame number you're currently clicking points on |
| Objects / Add Object / Clear Points (this frame) | You can track more than one object at a time (e.g. several cells in one run). "Add Object" creates a new target; "Clear Points (this frame)" removes only the points placed on the currently displayed frame |
| Clicking on the preview | Left-click adds a positive point (include this area); right-click adds a negative point (exclude this area) |

Placing points on more than one reference frame helps SAM2 track targets that change shape substantially over time. Clicking "Run" propagates the mask across all frames based on the points you've placed.

Output: one mask file per frame per object, named `mask_{3-digit frame number}_{object ID}.png` (or `.tif` if the source frames are TIFF), saved to the output folder. The preview shows the original frames with each mask overlaid in its assigned color.

### 3. Contour Extraction

Extracts an ordered outline (a sequence of x, y points) describing the cell's shape from the segmentation result.

| Field | Description |
|---|---|
| File name prefix / Number of frames | The target files and frame count |
| Mode: Filled mask (skimage) | Extracts the contour from a filled binary mask (`mask_NNN_<object ID>.ext`) produced by the Segmentation stage |
| Mode: Ordered outline (ImageJ) | Reads an already-ordered outline image instead, e.g. one produced in ImageJ |
| Resort distance threshold (d) | In Ordered outline mode, the distance threshold used to fix up points that are out of order |
| Tracked object ID (mask mode) | Which object's mask to use, matching the ID assigned in Segmentation |
| Save preview images (PNG) | Also saves a per-frame contour plot to an `images/` subfolder |

Output: a `.txt` file per frame containing the contour coordinates.

### 4. Trajectory Reordering

Smooths the raw contour points using a method suited to a closed curve, reducing the point-to-point noise left over from segmentation and contour extraction.

| Field | Description |
|---|---|
| File name prefix / Number of frames | The target files and frame count |
| Smoothing method: LOESS | Controlled by LOESS degree (polynomial order) and LOESS fraction (neighborhood size) |
| Smoothing method: Cyclic moving average | Controlled by the moving average window size |
| Save preview images (PNG) | Saves a before/after overlay plot per frame to an `images/` subfolder |

Output: a `.txt` file per frame containing the smoothed contour coordinates.

### 5. Centerline Extraction

Derives the cell's centerline, the axis along which it's elongating, from the smoothed contour.

| Field | Description |
|---|---|
| File name prefix / Number of frames | The target files and frame count |
| Extension length (o) | How far the centerline is extended beyond the contour, so the tip region is fully captured |
| Path trim start/end (m1 / m2) | The number of points trimmed off each end of the computed path, to remove unstable endpoints |
| Moving average window (mm) | An additional smoothing window applied along the centerline path |
| Save preview images (PNG) | Saves a contour + centerline overlay plot per frame to an `images/` subfolder |

Output: a `.txt` file per frame containing the centerline coordinates.

### 6. Kymograph

Samples brightness along the centerline and stacks the result over time into a kymograph: a space-versus-time map that shows how a fluorescent marker's distribution changes as the cell grows. Supports one or two channels, with a merged, color-composited image for two-channel data.

| Field | Description |
|---|---|
| File name prefix (Channel 1) / Number of channels | 1 or 2. A second channel gets its own input folder and file name prefix (a `_ch2` suggestion is filled in automatically but can be changed) |
| Channel 1 color / Channel 2 color | Display color for each channel, chosen from magenta / green / red / cyan / yellow / orange |
| Adjust color range to data max | Whether the brightness display range is automatically scaled to the data's maximum value |
| Mask directory / Tracked object ID | The Segmentation output folder and the object ID to sample. Use the object name assigned by "Add Object" in Segmentation (e.g. `obj0`) |
| Centerline directory | The Centerline output folder |
| Number of frames | How many frames to process |
| Normal sample length (px) | How far, perpendicular to the centerline, brightness is sampled at each point |
| Figure width / height (in) / Label font size | Appearance of the output image |
| Line width / Estimate optimal line width | The thickness of the strip drawn for each frame in the kymograph. "Estimate optimal line width" calculates a gap-free thickness from the figure size, frame count, and related settings, and fills it in for you. The calculated value can still leave a faint gap between strips, so add 1 to 2 pixels by hand if needed |
| Pixels per micron | Spatial calibration (pixels per micron) |
| Time interval / Time axis unit | The time between frames (minutes or seconds). Leave it unset to use the frame index on the time axis instead |

Output: intermediate brightness-profile data plus one kymograph image per channel (and a merged image for two-channel runs). Use the preview dropdown to switch between Channel 1, Channel 2, and Merged.

### 7. Growth

Computes cell length over time from the centerline data, derives growth rate from it, plots both (optionally LOWESS-smoothed), and exports a CSV summary.

| Field | Description |
|---|---|
| File name prefix (centerline) / Number of frames | The target files and frame count |
| Pixels per micron | Spatial calibration |
| Time interval (required) | The time between frames (minutes or seconds), required for this stage unlike Kymograph |
| Apply LOWESS smoothing / LOWESS degree / LOWESS fraction | Whether to smooth the cell-length and growth-rate series, and how strongly |
| Figure width / height (in) / Label font size | Appearance of the output plots |
| Preview plot | After a run, switch between Cell length, Growth rate, and Overlay |

Output: `{prefix}_growth.csv` (frame number, elapsed time, cell length, smoothed cell length, growth rate, and smoothed growth rate), plus three plot images: cell length, growth rate, and an overlay of both.

---

## 7. Plugins

### 7-1. Using plugins

Beyond the seven built-in stages, KymoTip can load user-added measurement tabs called plugins. These are useful for analyses outside the standard pipeline, such as measuring cell shape by a different metric, or the distribution of internal structures.

- Click the "**+ Plugins**" button at the top right of the tab bar to see a menu of the plugins currently available.
- Checking a plugin in that menu adds its tab; unchecking it, or closing the tab with its close button (×), removes the tab again (this doesn't delete any data).
- If no plugins are found, the "+ Plugins" button is disabled and its tooltip explains why.
- Plugins are picked up automatically once they're placed in the right folder, and no rebuild of KymoTip is required. That folder lives in your OS's per-user application data directory (on Windows, `%LOCALAPPDATA%\KymoTip\plugins`). Follow the instructions from wherever you obtained the plugin for how to install it there.
- If a plugin fails to load, a warning dialog reports the error at startup, and that plugin's tab simply doesn't appear.

### 7-2. Developing plugins (overview)

A KymoTip plugin is a tab built on the same framework as the built-in stages: input/output folders, a parameter form, and a Run button. The detailed technical specification is outside the scope of this manual.

The KymoTip repository includes a skill for developing plugins with Claude Code, which bundles the full specification and a working example.

- In the repository: `.claude/skills/kymotip-plugin-dev`
- The Windows installer also copies this folder into the installed application as `.claude/`, so plugin development is possible even if you only installed the prebuilt app and never cloned the repository.
- `gaussian_fit_detection` (object position/width detection via 1D Gaussian fitting) is a real-world example plugin, in addition to the minimal example bundled with the skill. It's available as a zip archive on the GitHub Releases page.

---

## 8. FAQ and Troubleshooting

**Q. The installer shows "Windows protected your PC."**
A. This warning appears because the installer isn't code-signed. Click "More info," then "Run anyway," to continue installing.

**Q. The SAM2 checkpoint download doesn't progress, or fails.**
A. Any checkpoint other than `tiny` is downloaded over the internet the first time you use it. Check your network connection, and if you're on a corporate network or behind a proxy, confirm that access to the download source isn't being blocked.

**Q. "Auto-detect from input directory" doesn't find anything.**
A. Check that the files in the folder actually follow the `{prefix}_{3-digit frame number}.{extension}` pattern (see [5. Input File Format and Naming](#5-input-file-format-and-naming)). If unrelated files (result images, hidden files, and so on) are mixed into the same folder, the wrong prefix can end up being detected.

**Q. Segmentation isn't tracking the target region well.**
A. Try clicking points on more than one reference frame, especially at points in time where the shape changes significantly, and double-check that each point is marked positive or negative correctly. Points placed by mistake can be cleared for the current frame only with "Clear Points (this frame)."

**Q. It's not clear whether Run is actually doing anything.**
A. As long as the progress bar is visible, a run is in progress. The Log panel also records start and finish messages, so check there too. If a run never seems to finish, look for an error message in the Log panel.

**Q. I want to adjust how the kymograph or growth plots look.**
A. Use the display-related parameters on each stage: "Figure width/height" and "Line width" on Kymograph, "Figure width/height" and "Label font size" on Growth. On Kymograph, "Estimate optimal line width" can suggest a reasonable strip thickness automatically.

---

## 9. Appendix

### Glossary

| Term | Description |
|---|---|
| Kymograph | An image that stacks a spatial brightness profile along the time axis, so you can see at a glance how a structure's position or intensity changes over time |
| Centerline | The line running through the middle of a cell's shape, representing its axis of elongation |
| Contour | An ordered sequence of coordinate points describing a cell's outline |
| Mask | A binary image marking the target region as 1 and everything else as 0 |
| SAM2 | A segmentation model for images and video developed by Meta; it tracks a target region automatically from points you click |
| LOESS / LOWESS | A local weighted regression technique used for smoothing, which suppresses noise while preserving the overall trend |

### Folder naming reference

| Folder | Contents |
|---|---|
| `00_raw` | Raw images (prepared by the user) |
| `01_registration` | Frames after alignment |
| `02_segmentation` | Masks produced by SAM2 |
| `03_contour` | Contour coordinate data |
| `04_trajectory` | Smoothed contour coordinate data |
| `05_centerline` | Centerline coordinate data |
| `06_kymograph` | Kymograph images and brightness profiles |
| `07_growth` | Growth-rate plots and CSV output |

### Segmentation canvas controls

| Action | Effect |
|---|---|
| Left-click | Add a positive point (include this area) |
| Right-click | Add a negative point (exclude this area) |
| Add Object | Adds a new tracking target (each gets its own color) |
| Clear Points (this frame) | Removes only the points placed on the currently displayed frame |
| Reference frame | Switches which frame you're placing points on. Placing points on multiple frames improves tracking accuracy |
