"""パイプライン共通のファイル命名規則・ディレクトリ管理・ログ追記ユーティリティ。

既存notebook群が使っていた "{fname}_{frame:03d}.拡張子" という3桁ゼロ埋め連番の
命名規則と、tab区切りの追記ログ("*_log.txt")の形式をそのまま踏襲する。
"""
from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path

import numpy as np

_FRAME_RE = re.compile(r"^(.+)_(\d{3})\.([A-Za-z0-9]+)$")


def frame_filename(fname: str, frame: int, ext: str) -> str:
    """既存notebook群と同じ "{fname}_{frame:03d}.{ext}" 形式のファイル名を返す。"""
    ext = ext.lstrip(".")
    return f"{fname}_{frame:03d}.{ext}"


def frame_path(directory: str | Path, fname: str, frame: int, ext: str) -> Path:
    return Path(directory) / frame_filename(fname, frame, ext)


def ensure_dir(directory: str | Path) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_image_any(path: str | Path) -> np.ndarray:
    """PIL経由で画像を読み込み、元のdtype(8bit/16bit問わず)のまま返す。

    cv2.imreadと違い16bit TIFFを8bitへ切り捨てないため、位置合わせ・輝度
    サンプリングなど画素値の精度が重要な処理はこちらを使う。
    """
    from PIL import Image

    with Image.open(path) as im:
        return np.array(im)


def write_image_any(path: str | Path, array: np.ndarray) -> None:
    """dtypeに応じてグレースケール画像を保存する(uint16ならそのまま16bit保存)。"""
    from PIL import Image

    path = Path(path)
    if array.dtype.kind == "u" and array.dtype.itemsize == 2:
        image = Image.fromarray(np.clip(np.rint(array), 0, 65535).astype(np.uint16))
    else:
        image = Image.fromarray(np.clip(np.rint(array), 0, 255).astype(np.uint8))
    image.save(path)


def normalize_for_display(array: np.ndarray) -> np.ndarray:
    """任意dtype(8bit/16bit等)の画素値を、表示用に0.5〜99.5パーセンタイルで
    コントラスト伸長したuint8配列に変換する(sam2_worker.load_frame_as_rgb8と同じ正規化)。
    """
    arr = array.astype(np.float64)
    lo, hi = np.percentile(arr, [0.5, 99.5])
    arr = np.clip((arr - lo) / max(hi - lo, 1e-6), 0, 1)
    return (arr * 255).astype(np.uint8)


def read_reference_image_size(base_dir: str | Path, fname: str) -> tuple[int, int] | None:
    """プロジェクトのbase_dir配下の01_registration/{fname}_000.*から画像サイズを読む。

    contour/trajectory/centerlineの各プレビューを、フレームごとに変動させず
    パイプライン全体の入力画像サイズに固定するための基準として使う。
    見つからなければNoneを返す。
    """
    registration_dir = Path(base_dir) / "01_registration"
    if not registration_dir.is_dir():
        return None
    matches = sorted(registration_dir.glob(f"{fname}_000.*"))
    if not matches:
        return None
    array = read_image_any(matches[0])
    height, width = array.shape[:2]
    return width, height


def save_xy_plot(
    out_path: str | Path,
    series: list[tuple[np.ndarray, np.ndarray, dict]],
    image_size: tuple[int, int] | None = None,
    dpi: float = 100.0,
) -> None:
    """(x, y)の折れ線プロットを、軸目盛・枠なしでプロットエリアのみPNG保存する
    (contour/trajectory/centerlineの画像出力オプション用)。

    seriesは(x, y, plot用kwargs)のリスト。centerlineの輪郭重ね描きのように
    複数系列を重ねたい場合はseriesに複数タプルを渡す。
    image_sizeを指定すると、元画像(mask/registration出力)のピクセルサイズと
    ちょうど同じピクセル数のPNGを出力する(元画像へのオーバーレイ用途を想定)。
    """
    from matplotlib.figure import Figure

    width, height = image_size if image_size is not None else (800, 600)
    fig = Figure(figsize=(width / dpi, height / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    for x, y, kwargs in series:
        ax.plot(x, y, **kwargs)
    if image_size is not None:
        ax.set_xlim(0, width)
        ax.set_ylim(height, 0)
    fig.savefig(out_path, format="png", dpi=dpi)


def discover_frames(directory: str | Path) -> tuple[str, str, int] | None:
    """入力ディレクトリを走査し、"{prefix}_{frame:03d}.{ext}" 形式のファイル群から
    最も出現数の多い (ファイル名prefix, 拡張子, フレーム数) を推定して返す。

    マッチするファイルが無ければNoneを返す。
    """
    directory = Path(directory)
    if not directory.is_dir():
        return None

    candidates: dict[tuple[str, str], set[int]] = {}
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        match = _FRAME_RE.match(entry.name)
        if not match:
            continue
        prefix, frame_str, ext = match.groups()
        candidates.setdefault((prefix, ext.lower()), set()).add(int(frame_str))

    if not candidates:
        return None

    best_key = max(candidates, key=lambda key: len(candidates[key]))
    prefix, ext = best_key
    num_frames = max(candidates[best_key]) + 1
    return prefix, ext, num_frames


def append_log(log_path: str | Path, columns: list[str], values: dict) -> None:
    """tab区切りの追記ログに1行書き込む。ファイルが無ければヘッダー行を先に書く。

    values は columns をキーとする辞書。timestamp列が columns に含まれる場合は
    自動的に現在時刻(ISO8601)を補完する。
    """
    log_path = Path(log_path)
    is_new = not log_path.is_file()
    row = dict(values)
    if "timestamp" in columns and "timestamp" not in row:
        row["timestamp"] = _dt.datetime.now().isoformat(timespec="seconds")

    ensure_dir(log_path.parent)
    with open(log_path, "a", encoding="utf-8") as f:
        if is_new:
            f.write("\t".join(columns) + "\n")
        f.write("\t".join(str(row.get(c, "")) for c in columns) + "\n")
