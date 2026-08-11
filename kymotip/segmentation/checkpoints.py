"""SAM2チェックポイントの入手先定義とオンデマンドダウンロード。

配布アプリには容量の都合上 `tiny` モデルのみを同梱する想定とし、
`small` / `base_plus` / `large` はユーザーが選択した時点でこのモジュールが
初回のみ自動ダウンロードする(2回目以降はローカルファイルをそのまま使う)。

ダウンロード元URLとファイル名は、sam2パッケージ本体が同梱している
`sam2/utils/download.py`(公式配布物)に記載された値をそのまま踏襲する。
"""
from __future__ import annotations

import urllib.request
from pathlib import Path
from typing import Callable

# sam2パッケージ同梱の sam2/utils/download.py に記載された公式配布元。
CHECKPOINT_BASE_URL = "https://dl.fbaipublicfiles.com/segment_anything_2/072824/"

CHECKPOINT_FILES = {
    "tiny": "sam2_hiera_tiny.pt",
    "small": "sam2_hiera_small.pt",
    "base_plus": "sam2_hiera_base_plus.pt",
    "large": "sam2_hiera_large.pt",
}

# アプリに同梱する(=ネットワーク接続なしで常に使える)想定のモデル。
BUNDLED_CHECKPOINTS = {"tiny"}

ProgressCallback = Callable[[int, int], None]


class CheckpointDownloadError(RuntimeError):
    pass


def checkpoint_path(sam2_root: str | Path, checkpoint: str) -> Path:
    """sam2_root配下でのチェックポイントファイルの想定パスを返す(存在確認はしない)。"""
    if checkpoint not in CHECKPOINT_FILES:
        raise ValueError(
            f"未知のチェックポイント名です: {checkpoint!r} "
            f"(選択可能: {sorted(CHECKPOINT_FILES)})"
        )
    return Path(sam2_root) / "sam2" / "weights" / CHECKPOINT_FILES[checkpoint]


def is_checkpoint_available(sam2_root: str | Path, checkpoint: str) -> bool:
    return checkpoint_path(sam2_root, checkpoint).is_file()


def ensure_checkpoint(
    sam2_root: str | Path,
    checkpoint: str,
    progress_callback: ProgressCallback | None = None,
) -> Path:
    """チェックポイントがローカルに無ければ公式配布元からダウンロードし、パスを返す。

    progress_callback(downloaded_bytes, total_bytes) はダウンロード中に繰り返し呼ばれる
    (GUI側で進捗バーに使う想定)。total_bytesはサーバーが返さない場合0になりうる。
    """
    path = checkpoint_path(sam2_root, checkpoint)
    if path.is_file():
        return path

    if checkpoint in BUNDLED_CHECKPOINTS:
        raise CheckpointDownloadError(
            f"同梱されているはずの'{checkpoint}'モデルが見つかりません: {path}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    url = CHECKPOINT_BASE_URL + CHECKPOINT_FILES[checkpoint]
    tmp_path = path.with_name(path.name + ".part")

    def _reporthook(block_num: int, block_size: int, total_size: int) -> None:
        if progress_callback is not None:
            downloaded = min(block_num * block_size, total_size) if total_size > 0 else block_num * block_size
            progress_callback(downloaded, max(total_size, 0))

    try:
        urllib.request.urlretrieve(url, tmp_path, reporthook=_reporthook)
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        raise CheckpointDownloadError(
            f"'{checkpoint}'モデルのダウンロードに失敗しました(URL: {url}): {exc}"
        ) from exc

    tmp_path.replace(path)
    return path
