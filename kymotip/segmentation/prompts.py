"""SAM2の点プロンプト(標的=positive / 除外=negative)のデータ構造と、
前フレームのマスクから次フレーム用プロンプトを自動生成する伝播ロジック。
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class PointPrompt:
    x: float
    y: float
    label: int  # 1=標的(positive), 0=除外(negative)


@dataclass
class FramePrompt:
    points: list[PointPrompt] = field(default_factory=list)
    box: tuple[float, float, float, float] | None = None  # (x0, y0, x1, y1)

    def to_dict(self) -> dict:
        return {
            "points": [{"x": p.x, "y": p.y, "label": p.label} for p in self.points],
            "box": list(self.box) if self.box is not None else None,
        }

    @staticmethod
    def from_dict(d: dict) -> "FramePrompt":
        points = [PointPrompt(p["x"], p["y"], p["label"]) for p in d.get("points", [])]
        box = tuple(d["box"]) if d.get("box") is not None else None
        return FramePrompt(points=points, box=box)


def propagate_prompt(
    prev_mask: np.ndarray,
    negative_points: list[PointPrompt],
    box_margin: float = 0.1,
) -> FramePrompt:
    """前フレームのマスクから次フレーム用の FramePrompt を自動生成する。

    前フレームのマスク重心を新たなpositive点として追加し、ユーザーが最初に
    指定したnegative点(除外領域は静的な背景構造を想定)は全フレーム共通で
    引き継ぐ。bboxはマージン付きで前フレームのマスクから再計算する。
    """
    ys, xs = np.where(prev_mask)
    if len(xs) == 0:
        raise ValueError("previous mask is empty; cannot propagate prompt")

    centroid_x, centroid_y = float(xs.mean()), float(ys.mean())
    x0, y0, x1, y1 = float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
    w, h = x1 - x0, y1 - y0
    box = (
        x0 - box_margin * w,
        y0 - box_margin * h,
        x1 + box_margin * w,
        y1 + box_margin * h,
    )
    points = [PointPrompt(centroid_x, centroid_y, 1), *negative_points]
    return FramePrompt(points=points, box=box)
