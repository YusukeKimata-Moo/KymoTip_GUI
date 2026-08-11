"""sam2環境のpython.exe(または python3)が直接実行するワーカースクリプト。

GUIプロセス(kymotip.segmentation.launcher)からsubprocessで起動され、
JSON形式のリクエストファイルを1つ受け取り、全フレームの自動セグメンテーション
バッチを実行して、マスクPNGとJSON結果を書き出す。

このファイルはsam2用micromamba環境の中で単独実行されるため、他のkymotip
モジュール(kymotip.core等)には依存しない自己完結スクリプトとする(GUI側の
親プロセスとPython実行環境が異なるため)。

リクエストJSONの形式(複数オブジェクト・複数リファレンスフレーム対応):
{
  "sam2_root": "<sam2環境のルートディレクトリ>",
  "checkpoint": "tiny" | "small" | "base_plus" | "large",
  "frames": ["<frame0のパス>", "<frame1のパス>", ...],
  "output_dir": "<マスクPNG等の出力先ディレクトリ>",
  "objects": {
    "obj0": {
      "0": {"points": [{"x":.., "y":.., "label":1|0}, ...], "box": [x0,y0,x1,y1] | null},
      "45": {...}
    },
    "obj1": {...},
    ...
  } | null,
  "box_margin": 0.1
}
各オブジェクトは1つ以上の「リファレンスフレーム」(フレーム番号→点プロンプト)を持つ。
最も若いリファレンスフレームからそのオブジェクトの追跡を開始し、以降は前フレームの
マスク重心をpositive点として伝播する。最初のリファレンスフレームがフレーム0でない
場合は、そのフレームより前の区間についても同じ伝播ロジックを逆方向(フレーム番号が
小さくなる向き)に適用し、動画の先頭側もカバーする。リファレンスフレームが複数ある
場合、区間内は左側(若い方)のリファレンスフレームからの前方伝播のみを用いる(追跡が
崩れた地点に新しいリファレンスフレームを追加すると、そのフレームで前方伝播を上書きして
再アンカリングできる)。あるオブジェクトのマスクが空になった場合、そのオブジェクトの
それ以降(または前方パスなら以前)の処理を打ち切るが、後続の明示的なリファレンス
フレームに到達すれば再アンカリングにより復活する。
"objects" が null/空の場合、Otsu閾値による自動初期化(検証②のロジック)でフレーム0を
リファレンスとする単一オブジェクト"obj0"として扱う。

マスク出力(mask_{frame:03d}_{object_id}.拡張子)は、元フレームの拡張子が.tif/.tiffなら
.tif、それ以外なら.pngとして8bit二値画像で保存する(入力の画像フォーマットを維持する)。
"""
from __future__ import annotations

import json
import os
import sys
import time

CHECKPOINT_MAP = {
    "tiny": ("sam2_hiera_tiny.pt", "sam2_hiera_t.yaml"),
    "small": ("sam2_hiera_small.pt", "sam2_hiera_s.yaml"),
    "base_plus": ("sam2_hiera_base_plus.pt", "sam2_hiera_b+.yaml"),
    "large": ("sam2_hiera_large.pt", "sam2_hiera_l.yaml"),
}


def load_frame_as_rgb8(path):
    import numpy as np
    from PIL import Image

    arr = np.array(Image.open(path)).astype(np.float64)
    lo, hi = np.percentile(arr, [0.5, 99.5])
    arr = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1)
    img8 = (arr * 255).astype("uint8")
    return np.stack([img8] * 3, axis=-1)


def largest_component_bbox(mask):
    import numpy as np
    from scipy import ndimage

    labeled, n = ndimage.label(mask)
    if n == 0:
        return None
    sizes = ndimage.sum(mask, labeled, range(1, n + 1))
    best = int(np.argmax(sizes)) + 1
    comp = labeled == best
    ys, xs = np.where(comp)
    bbox = (float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max()))
    centroid = (float(xs.mean()), float(ys.mean()))
    area = int(comp.sum())
    return bbox, centroid, area, comp


def otsu_initial_prompt(img_rgb):
    from skimage.filters import threshold_otsu

    gray = img_rgb[..., 0]
    thr = threshold_otsu(gray)
    mask = gray > thr
    result = largest_component_bbox(mask)
    if result is None:
        raise RuntimeError("Otsu thresholding produced an empty mask for frame 0")
    bbox, centroid, _area, _comp = result
    return {
        "points": [{"x": centroid[0], "y": centroid[1], "label": 1}],
        "box": list(bbox),
    }


def mask_extension(frame_path):
    """マスクの保存拡張子を、元フレームの拡張子(png/tif/tiff)に合わせて決める
    (ビット深度は常に8bitの二値マスクとして保存する)。"""
    ext = os.path.splitext(frame_path)[1].lower()
    return ".tif" if ext in (".tif", ".tiff") else ".png"


def propagate_prompt(prev_mask, negative_points, box_margin):
    import numpy as np

    ys, xs = np.where(prev_mask)
    if len(xs) == 0:
        raise RuntimeError("previous mask is empty; cannot propagate prompt")
    centroid_x, centroid_y = float(xs.mean()), float(xs.mean() * 0 + ys.mean())
    x0, y0, x1, y1 = float(xs.min()), float(ys.min()), float(xs.max()), float(ys.max())
    w, h = x1 - x0, y1 - y0
    box = [
        x0 - box_margin * w,
        y0 - box_margin * h,
        x1 + box_margin * w,
        y1 + box_margin * h,
    ]
    points = [{"x": centroid_x, "y": centroid_y, "label": 1}, *negative_points]
    return {"points": points, "box": box}


def run_batch(request: dict) -> dict:
    import numpy as np
    from PIL import Image

    sam2_root = request["sam2_root"]
    checkpoint_name = request.get("checkpoint", "tiny")
    frames = request["frames"]
    output_dir = request["output_dir"]
    box_margin = request.get("box_margin", 0.1)
    objects_raw = request.get("objects") or None

    os.makedirs(output_dir, exist_ok=True)

    ckpt_file, cfg_name = CHECKPOINT_MAP[checkpoint_name]
    ckpt_path = os.path.join(sam2_root, "sam2", "weights", ckpt_file)

    sys.path.insert(0, os.path.join(sam2_root, "Lib", "site-packages"))
    os.chdir(os.path.join(sam2_root, "Lib", "site-packages", "sam2"))

    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor

    model = build_sam2(cfg_name, ckpt_path, device="cpu")
    predictor = SAM2ImagePredictor(model)

    n_frames = len(frames)

    # objects が指定されていなければ、Otsu自動初期化によるフレーム0リファレンスの
    # 単一オブジェクト"obj0"として扱う(refはNoneで「Otsuで計算する」を表す)。
    use_otsu = not objects_raw
    if use_otsu:
        reference_frames = {"obj0": {0: None}}
    else:
        reference_frames = {
            object_id: {int(idx): prompt for idx, prompt in frame_map.items()}
            for object_id, frame_map in objects_raw.items()
        }
    first_ref = {object_id: min(ref_map) for object_id, ref_map in reference_frames.items()}

    results_by_frame: dict[int, dict] = {}

    def record(i, object_id, info):
        results_by_frame.setdefault(i, {})[object_id] = info

    def predict_and_save(img_rgb, prompt, i, object_id, frame_path):
        predictor.set_image(img_rgb)
        point_coords = np.array([[p["x"], p["y"]] for p in prompt["points"]])
        point_labels = np.array([p["label"] for p in prompt["points"]])
        box = np.array([prompt["box"]]) if prompt.get("box") else None

        t0 = time.perf_counter()
        masks, scores, _ = predictor.predict(
            point_coords=point_coords,
            point_labels=point_labels,
            box=box,
            multimask_output=False,
        )
        elapsed = time.perf_counter() - t0
        mask = masks[0].astype(bool)

        result = largest_component_bbox(mask)
        if result is None:
            return None, {"ok": False, "error": "empty mask"}

        _bbox, centroid, area, comp = result
        ext = mask_extension(frame_path)
        mask_path = os.path.join(output_dir, f"mask_{i:03d}_{object_id}{ext}")
        Image.fromarray((comp.astype("uint8") * 255)).save(mask_path)
        info = {
            "ok": True,
            "mask_path": mask_path,
            "area": area,
            "centroid": list(centroid),
            "score": float(scores[0]),
            "time_sec": round(elapsed, 2),
        }
        return comp, info

    t_total0 = time.perf_counter()

    # 前方パス: 各オブジェクトの最初のリファレンスフレームから末尾に向けて処理する。
    # 明示的なリファレンスフレームに到達するたびに前方伝播を上書きして再アンカリングする。
    prev_mask: dict = {}
    negative_points: dict = {}
    active: set = set()
    mask_at_first_ref: dict = {}
    negs_at_first_ref: dict = {}

    for i in range(n_frames):
        img_rgb = None
        for object_id, ref_map in reference_frames.items():
            fr0 = first_ref[object_id]
            if i < fr0:
                continue
            has_ref_here = i in ref_map
            if not has_ref_here and object_id not in active:
                continue

            if img_rgb is None:
                img_rgb = load_frame_as_rgb8(frames[i])

            if has_ref_here:
                ref_prompt = ref_map[i]
                prompt = otsu_initial_prompt(img_rgb) if ref_prompt is None else ref_prompt
                negative_points[object_id] = [p for p in prompt["points"] if p["label"] == 0]
                active.add(object_id)
            else:
                prompt = propagate_prompt(prev_mask[object_id], negative_points.get(object_id, []), box_margin)

            comp, info = predict_and_save(img_rgb, prompt, i, object_id, frames[i])
            record(i, object_id, info)
            if comp is None:
                active.discard(object_id)
                prev_mask.pop(object_id, None)
                continue

            prev_mask[object_id] = comp
            if i == fr0:
                mask_at_first_ref[object_id] = comp
                negs_at_first_ref[object_id] = negative_points[object_id]

    # 後方パス: 最初のリファレンスフレームがフレーム0でないオブジェクトについて、
    # そのリファレンスフレームのマスクを起点に逆方向へ伝播する。
    backward_objects = {
        object_id: fr0 for object_id, fr0 in first_ref.items() if fr0 > 0 and object_id in mask_at_first_ref
    }
    if backward_objects:
        prev_mask_b = dict(mask_at_first_ref)
        negative_points_b = dict(negs_at_first_ref)
        active_b = set(backward_objects.keys())
        max_first_ref = max(backward_objects.values())

        for i in range(max_first_ref - 1, -1, -1):
            img_rgb = None
            for object_id, fr0 in backward_objects.items():
                if i >= fr0 or object_id not in active_b:
                    continue
                if img_rgb is None:
                    img_rgb = load_frame_as_rgb8(frames[i])
                prompt = propagate_prompt(prev_mask_b[object_id], negative_points_b.get(object_id, []), box_margin)
                comp, info = predict_and_save(img_rgb, prompt, i, object_id, frames[i])
                record(i, object_id, info)
                if comp is None:
                    active_b.discard(object_id)
                    continue
                prev_mask_b[object_id] = comp

    t_total = time.perf_counter() - t_total0
    frame_results = [{"frame": i, "objects": results_by_frame.get(i, {})} for i in range(n_frames)]
    n_frames_with_data = sum(1 for r in frame_results if r["objects"])

    return {
        "ok": True,
        "python_exe": sys.executable,
        "n_frames": n_frames_with_data,
        "total_time_sec": round(t_total, 2),
        "frames": frame_results,
    }


def main():
    request_path = sys.argv[1]
    with open(request_path, "r", encoding="utf-8") as f:
        request = json.load(f)

    try:
        result = run_batch(request)
    except Exception as exc:  # ワーカーの失敗を必ずJSONとして親プロセスへ返す
        import traceback
        result = {"ok": False, "error": str(exc), "traceback": traceback.format_exc()}

    print("__RESULT_JSON__" + json.dumps(result))


if __name__ == "__main__":
    main()
