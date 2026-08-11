"""Stage 2: SAM2 segmentation panel with multi-object point-prompt canvas."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGraphicsEllipseItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...segmentation.launcher import SegmentationError, run_segmentation
from ...segmentation.prompts import FramePrompt, PointPrompt
from ..settings import AppSettings
from .base import DirPicker, StageWidgetBase

OBJECT_COLORS = [
    QColor("#2ecc71"),
    QColor("#3498db"),
    QColor("#e67e22"),
    QColor("#e84393"),
    QColor("#9b59b6"),
    QColor("#f1c40f"),
]

POINT_RADIUS = 5


def _load_preview_pixmap(path: str) -> QPixmap:
    """16bit TIFF等、QPixmapが直接読めない形式でもプレビュー表示できるように、
    percentileコントラスト伸長で8bit化してからQImageに変換する
    (sam2_worker.load_frame_as_rgb8と同じ正規化ロジック)。
    """
    import numpy as np
    from PIL import Image

    arr = np.array(Image.open(path)).astype(np.float64)
    lo, hi = np.percentile(arr, [0.5, 99.5])
    arr = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1)
    img8 = (arr * 255).astype(np.uint8)
    if img8.ndim == 2:
        h, w = img8.shape
        qimage = QImage(img8.tobytes(), w, h, w, QImage.Format_Grayscale8)
    else:
        h, w = img8.shape[:2]
        rgb = np.ascontiguousarray(img8[:, :, :3])
        qimage = QImage(rgb.tobytes(), w, h, w * 3, QImage.Format_RGB888)
    return QPixmap.fromImage(qimage)


class ClickableGraphicsView(QGraphicsView):
    point_clicked = Signal(float, float, int)  # x, y, label (1=positive, 0=negative)

    def mousePressEvent(self, event) -> None:
        scene_pos: QPointF = self.mapToScene(event.pos())
        if event.button() == Qt.LeftButton:
            self.point_clicked.emit(scene_pos.x(), scene_pos.y(), 1)
        elif event.button() == Qt.RightButton:
            self.point_clicked.emit(scene_pos.x(), scene_pos.y(), 0)
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.scene().sceneRect().isEmpty():
            self.fitInView(self.scene().sceneRect(), Qt.KeepAspectRatio)


class SegmentationStage(StageWidgetBase):
    stage_title = "Segmentation (SAM2)"
    tab_label = "Segmentation"
    plugin_order = 2
    download_progress = Signal(int, int)

    def wire_project(self, base_dir: Path, fname: str) -> None:
        self.input_dir_picker.set_path(str(base_dir / "01_registration"))
        self.output_dir_picker.set_path(str(base_dir / "02_segmentation"))

    def __init__(self, parent: QWidget | None = None) -> None:
        self._objects: dict[str, dict[int, list[PointPrompt]]] = {}
        self._object_colors: dict[str, QColor] = {}
        self._object_list_items: dict[str, QListWidgetItem] = {}
        self._active_object_id: str | None = None
        self._frames: list[str] = []
        self._current_ref_frame = 0
        self._pixmap_item = None
        self._point_items: list[QGraphicsEllipseItem] = []
        self._settings = AppSettings()
        self._last_output_dir = None
        self._last_active_object_ids: list[str] = []

        super().__init__(parent)

        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        self.download_progress.connect(self._on_download_progress)

    def build_parameter_form(self, form_layout: QFormLayout) -> None:
        self.sam2_root_picker = DirPicker("SAM2 environment root")
        self.sam2_root_picker.set_path(self._settings.sam2_root)
        self.sam2_root_picker.edit.textChanged.connect(self._on_sam2_root_changed)
        form_layout.addRow("SAM2 environment root", self.sam2_root_picker)

        self.checkpoint_combo = QComboBox()
        self.checkpoint_combo.addItems(["tiny", "small", "base_plus", "large"])
        form_layout.addRow("Checkpoint", self.checkpoint_combo)

        load_frames_button = QPushButton("Load Frames from Input Directory")
        load_frames_button.clicked.connect(self._load_frames)
        form_layout.addRow(load_frames_button)

        self.ref_frame_spin = QSpinBox()
        self.ref_frame_spin.setRange(0, 0)
        self.ref_frame_spin.setEnabled(False)
        self.ref_frame_spin.valueChanged.connect(self._show_frame)
        form_layout.addRow("Reference frame", self.ref_frame_spin)

        self.object_list = QListWidget()
        self.object_list.currentItemChanged.connect(self._on_active_object_changed)
        form_layout.addRow("Objects", self.object_list)

        object_buttons = QWidget()
        object_buttons_layout = QHBoxLayout(object_buttons)
        object_buttons_layout.setContentsMargins(0, 0, 0, 0)
        add_object_button = QPushButton("Add Object")
        add_object_button.clicked.connect(self._add_object)
        clear_points_button = QPushButton("Clear Points (this frame)")
        clear_points_button.clicked.connect(self._clear_active_object_points)
        object_buttons_layout.addWidget(add_object_button)
        object_buttons_layout.addWidget(clear_points_button)
        form_layout.addRow(object_buttons)

        self.canvas_view = ClickableGraphicsView()
        self.canvas_scene = QGraphicsScene(self.canvas_view)
        self.canvas_view.setScene(self.canvas_scene)
        self.canvas_view.setMinimumHeight(500)
        self.canvas_view.point_clicked.connect(self._on_canvas_clicked)
        form_layout.addRow(QLabel("Left click = positive, Right click = negative"))
        form_layout.addRow(self.canvas_view)

    def _load_frames(self) -> None:
        input_dir = self.input_dir_picker.path()
        if not input_dir:
            QMessageBox.warning(self, "Invalid input", "Input directory is required.")
            return
        frames = sorted(
            str(p)
            for ext in ("*.png", "*.tif", "*.tiff")
            for p in Path(input_dir).glob(ext)
        )
        if not frames:
            QMessageBox.warning(self, "No frames found", f"No PNG/TIFF frames found in {input_dir}.")
            return
        self._frames = frames

        self.ref_frame_spin.blockSignals(True)
        self.ref_frame_spin.setRange(0, len(frames) - 1)
        self.ref_frame_spin.setValue(0)
        self.ref_frame_spin.setEnabled(len(frames) > 1)
        self.ref_frame_spin.blockSignals(False)

        self.log(f"Loaded {len(frames)} frames.")
        self._show_frame(0)

    def _show_frame(self, index: int) -> None:
        if not self._frames or not (0 <= index < len(self._frames)):
            return
        self._current_ref_frame = index

        pixmap = _load_preview_pixmap(self._frames[index])
        self.canvas_scene.clear()
        self._point_items = []
        self._pixmap_item = self.canvas_scene.addPixmap(pixmap)
        self.canvas_scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())
        self.canvas_view.fitInView(self.canvas_scene.sceneRect(), Qt.KeepAspectRatio)
        self._redraw_points()

    def _add_object(self) -> None:
        object_id = f"obj{len(self._objects)}"
        color = OBJECT_COLORS[len(self._objects) % len(OBJECT_COLORS)]
        self._objects[object_id] = {}
        self._object_colors[object_id] = color

        item = QListWidgetItem(object_id)
        item.setForeground(QBrush(color))
        self._object_list_items[object_id] = item
        self.object_list.addItem(item)
        self.object_list.setCurrentItem(item)

    def _on_active_object_changed(self, current: QListWidgetItem | None, _previous) -> None:
        self._active_object_id = current.text() if current is not None else None

    def _clear_active_object_points(self) -> None:
        if self._active_object_id is None:
            return
        self._objects[self._active_object_id].pop(self._current_ref_frame, None)
        self._update_object_list_label(self._active_object_id)
        self._redraw_points()

    def _on_canvas_clicked(self, x: float, y: float, label: int) -> None:
        if self._active_object_id is None:
            QMessageBox.information(self, "No active object", "Add an object first.")
            return
        frame_map = self._objects[self._active_object_id]
        frame_map.setdefault(self._current_ref_frame, []).append(PointPrompt(x=x, y=y, label=label))
        self._update_object_list_label(self._active_object_id)
        self._redraw_points()

    def _update_object_list_label(self, object_id: str) -> None:
        item = self._object_list_items.get(object_id)
        if item is None:
            return
        ref_frames = sorted(fr for fr, pts in self._objects[object_id].items() if pts)
        if ref_frames:
            item.setText(f"{object_id} (frames: {', '.join(str(fr) for fr in ref_frames)})")
        else:
            item.setText(object_id)

    def _redraw_points(self) -> None:
        for item in self._point_items:
            self.canvas_scene.removeItem(item)
        self._point_items = []

        for object_id, frame_map in self._objects.items():
            color = self._object_colors[object_id]
            for point in frame_map.get(self._current_ref_frame, []):
                pen = QPen(color)
                brush = QBrush(color) if point.label == 1 else QBrush(Qt.NoBrush)
                ellipse = self.canvas_scene.addEllipse(
                    point.x - POINT_RADIUS,
                    point.y - POINT_RADIUS,
                    POINT_RADIUS * 2,
                    POINT_RADIUS * 2,
                    pen,
                    brush,
                )
                self._point_items.append(ellipse)

    def _on_sam2_root_changed(self, value: str) -> None:
        self._settings.sam2_root = value

    def _on_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, total)
            self.progress_bar.setValue(downloaded)
        else:
            self.progress_bar.setRange(0, 0)

    def build_task(self):
        if not self._frames:
            raise ValueError("Load frames from the input directory first.")
        active_objects = {
            oid: {fr: pts for fr, pts in frame_map.items() if pts}
            for oid, frame_map in self._objects.items()
        }
        active_objects = {oid: fm for oid, fm in active_objects.items() if fm}
        if not active_objects:
            raise ValueError(
                "Add at least one object and click positive points on at least one reference frame."
            )

        sam2_root = self.sam2_root_picker.path()
        if not sam2_root:
            raise ValueError("SAM2 environment root is required.")

        output_dir = self.ensure_output_dir()
        self._last_output_dir = output_dir
        self._last_active_object_ids = list(active_objects.keys())
        checkpoint = self.checkpoint_combo.currentText()

        initial_prompts = {
            object_id: {frame_idx: FramePrompt(points=points) for frame_idx, points in frame_map.items()}
            for object_id, frame_map in active_objects.items()
        }
        frames = self._frames

        def task():
            self.progress_bar.setRange(0, 0)
            try:
                return run_segmentation(
                    sam2_root=sam2_root,
                    frames=frames,
                    output_dir=str(output_dir),
                    initial_prompts=initial_prompts,
                    checkpoint=checkpoint,
                    download_progress_callback=lambda done, total: self.download_progress.emit(done, total),
                )
            except SegmentationError as exc:
                raise RuntimeError(str(exc)) from exc

        return task

    def on_task_finished(self, result) -> None:
        n_frames = result.get("n_frames", 0)
        total_time = result.get("total_time_sec", 0)
        self.log(f"Processed {n_frames} frames in {total_time:.1f}s.")

        if not self._frames or self._last_output_dir is None:
            return

        frames = self._frames
        output_dir = self._last_output_dir
        object_ids = self._last_active_object_ids
        object_colors = self._object_colors

        def render(index: int) -> None:
            import numpy as np
            from PIL import Image

            from ...core.io_utils import normalize_for_display, read_image_any

            base = normalize_for_display(read_image_any(frames[index]))
            rgb = np.stack([base] * 3, axis=-1) if base.ndim == 2 else base[:, :, :3].copy()
            overlay = rgb.astype(np.float64)

            frame_ext = Path(frames[index]).suffix.lower()
            mask_ext = ".tif" if frame_ext in (".tif", ".tiff") else ".png"
            for object_id in object_ids:
                mask_path = Path(output_dir) / f"mask_{index:03d}_{object_id}{mask_ext}"
                if not mask_path.exists():
                    continue
                mask = np.array(Image.open(mask_path)) > 0
                color = object_colors.get(object_id)
                if color is None:
                    continue
                color_rgb = np.array([color.red(), color.green(), color.blue()], dtype=np.float64)
                overlay[mask] = overlay[mask] * 0.4 + color_rgb * 0.6

            self.preview.show_image(np.clip(overlay, 0, 255).astype(np.uint8))

        self.preview.set_frames(len(frames), render)
