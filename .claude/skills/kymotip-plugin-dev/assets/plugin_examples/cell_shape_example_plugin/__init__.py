"""Example plugin: measures area and perimeter from segmentation masks.

Usage: copy this whole folder into plugins/ at the repository root
(created automatically if missing), then rename the folder and rewrite the
class name and logic. plugins/ is already .gitignore'd, so feel free to
experiment freely. See
.claude/skills/kymotip-plugin-dev/references/PLUGIN_SPEC.md for the full
specification.

Only use names exported from kymotip.plugin_api; never import
kymotip.core / kymotip.gui internal modules directly.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QFormLayout, QLineEdit, QSpinBox

from kymotip.plugin_api import (
    StageWidgetBase,
    append_log,
    ensure_dir,
    read_image_any,
)


class CellShapeExampleStage(StageWidgetBase):
    """Minimal example that computes per-frame area (px) and perimeter (px)
    from 02_segmentation mask images and writes them to a tab-separated log.
    """

    stage_title = "Cell Shape (example)"
    # Used for ordering within the "Plugins" menu. Doesn't need to avoid
    # colliding with the built-in stages (1-7); an in-between value is a
    # common convention.
    plugin_order = 2.5
    plugin_api_version = 1

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.input_dir_picker.set_path(str(base_dir / "02_segmentation"))
        self.output_dir_picker.set_path(str(base_dir / "cell_shape_example"))

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.object_id_edit = QLineEdit()
        form_layout.addRow("Object ID (from Segmentation stage)", self.object_id_edit)

        self.num_frames_spin = QSpinBox()
        self.num_frames_spin.setRange(1, 100000)
        self.num_frames_spin.setValue(10)
        form_layout.addRow("Number of frames", self.num_frames_spin)

    def build_task(self):
        object_id = self.object_id_edit.text().strip()
        if not object_id:
            raise ValueError("Object ID is required.")
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            raise ValueError("Input directory is required.")
        output_dir = self.output_dir_picker.path()
        if not output_dir:
            raise ValueError("Output directory is required.")
        num_frames = self.num_frames_spin.value()

        def task():
            out_dir = ensure_dir(output_dir)
            log_path = Path(out_dir) / f"{object_id}_cell_shape.tsv"
            columns = ["frame", "area_px", "perimeter_px"]
            for frame in range(num_frames):
                # The built-in Segmentation stage writes masks named
                # mask_NNN_<object_id>.<ext> (tif if the source frames are
                # tif/tiff, png otherwise).
                matches = sorted(Path(input_dir).glob(f"mask_{frame:03d}_{object_id}.*"))
                if not matches:
                    raise FileNotFoundError(
                        f"No mask found for frame {frame}, object '{object_id}' in {input_dir}"
                    )
                mask = read_image_any(matches[0]) > 0
                area = int(np.count_nonzero(mask))

                # Pad the image border with background before checking
                # 4-connectivity (np.roll would wrap around and treat the
                # opposite edge as a neighbor, misclassifying the border as
                # interior).
                padded = np.pad(mask, 1, mode="constant", constant_values=False)
                interior = (
                    padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
                )
                perimeter = int(np.count_nonzero(mask & ~interior))

                append_log(
                    log_path, columns, {"frame": frame, "area_px": area, "perimeter_px": perimeter}
                )
            return str(log_path)

        return task

    def on_task_finished(self, result) -> None:
        self.log(f"Saved: {result}")
