# Cell Shape (example) plugin

A minimal example plugin that computes per-frame area (px) and perimeter
(px) from `02_segmentation` mask images and writes them to a
tab-separated (`.tsv`) log.

Copy this whole folder as a template when starting a new plugin.

## Usage

1. Copy this folder into `plugins/` at the repository root (created
   automatically if missing).
2. Rewrite the folder name, the class name in `__init__.py`, and the
   processing logic to match the measurement you want.
3. Restart the KymoTip GUI; the plugin appears in the toolbar's "Plugins"
   menu.

## Input

- Object ID: the name automatically assigned to an object by the
  Segmentation stage (`obj0`, `obj1`, ...). Reads from
  `02_segmentation/mask_NNN_<object_id>.<ext>`.
- Number of frames: how many frames to process.

## Output

`cell_shape_example/<object_id>_cell_shape.tsv`
(columns: `frame`, `area_px`, `perimeter_px`)

See `.claude/skills/kymotip-plugin-dev/references/PLUGIN_SPEC.md` for the
full specification.
