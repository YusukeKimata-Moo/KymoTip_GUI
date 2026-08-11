"""GUI(メイン)プロセス側からsam2_worker.pyをsubprocess起動するランチャ。

検証事項4のPoC(scratchpad/gui_launcher_poc.py)で確認した通り、`appose`は
不要で、素の`subprocess.run([python_exe_abs_path, worker_script, ...])`だけで
sam2用micromamba環境を起動できる。conda関連のPATH/環境変数がなくても、
Windowsは環境ディレクトリ自身からtorch/numpyのDLLを解決できるため動作する。

Mac対応: `sys.platform`により実行ファイル名(`python.exe`/`bin/python3`)を
切り替える。Windowsと対称なsubprocess起動パターンであり、conda-forge/pytorch
のdylib解決はconda環境の標準機構(rpath埋め込み)でWindowsのDLL探索順序より
本来頑健なはずだが、Mac実機での検証はまだ行っていない(未検証)。
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .checkpoints import ProgressCallback, ensure_checkpoint
from .prompts import FramePrompt


class SegmentationError(RuntimeError):
    pass


def resolve_python_exe(sam2_root: str | Path) -> Path:
    """sam2環境ルートから python実行ファイルの絶対パスを解決する。

    Windows: <sam2_root>/python.exe
    Mac(未検証): <sam2_root>/bin/python3
    """
    sam2_root = Path(sam2_root)
    if sys.platform == "win32":
        exe = sam2_root / "python.exe"
    else:
        exe = sam2_root / "bin" / "python3"
    if not exe.is_file():
        raise SegmentationError(f"sam2環境のpython実行ファイルが見つかりません: {exe}")
    return exe


def run_segmentation(
    sam2_root: str | Path,
    frames: list[str],
    output_dir: str | Path,
    initial_prompts: dict[str, dict[int, FramePrompt]] | None,
    checkpoint: str = "tiny",
    box_margin: float = 0.1,
    timeout: float | None = None,
    download_progress_callback: ProgressCallback | None = None,
) -> dict:
    """sam2_worker.pyをsubprocessで起動し、全フレーム・全オブジェクトのセグメンテーション結果を返す。

    initial_prompts はオブジェクトID(例: "obj0", "obj1", ...)をキーとし、値はさらに
    「リファレンスフレーム番号 -> FramePrompt」の辞書。各オブジェクトは自身の最初の
    リファレンスフレームから追跡を開始し(フレーム0でなければその前方区間へも逆方向に
    伝播する)、以降のリファレンスフレームで前方伝播を上書きして再アンカリングする。
    None/空の場合、worker側でOtsu閾値による自動初期化(単一オブジェクト、フレーム0起点)
    にフォールバックする。
    checkpointが'tiny'以外でローカルに未取得の場合、サブプロセス起動前にこの関数(GUI/メイン
    プロセス側)が公式配布元から自動ダウンロードする(初回のみ。以降はローカルファイルを再利用)。
    """
    python_exe = resolve_python_exe(sam2_root)
    worker_script = Path(__file__).with_name("sam2_worker.py")

    ensure_checkpoint(sam2_root, checkpoint, progress_callback=download_progress_callback)

    request = {
        "sam2_root": str(sam2_root),
        "checkpoint": checkpoint,
        "frames": [str(f) for f in frames],
        "output_dir": str(output_dir),
        "objects": (
            {
                object_id: {str(frame_idx): prompt.to_dict() for frame_idx, prompt in frame_map.items()}
                for object_id, frame_map in initial_prompts.items()
            }
            if initial_prompts
            else None
        ),
        "box_margin": box_margin,
    }

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", encoding="utf-8", delete=False
    ) as f:
        json.dump(request, f, ensure_ascii=False)
        request_path = f.name

    # Windowsではコンソール版python.exeをGUI(コンソールなし)プロセスから
    # 起動すると、既定で新しいコンソールウィンドウが一瞬表示されてしまうため
    # 抑制する。
    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    try:
        proc = subprocess.run(
            [str(python_exe), str(worker_script), request_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
        )
    finally:
        Path(request_path).unlink(missing_ok=True)

    result_line = None
    for line in proc.stdout.splitlines():
        if line.startswith("__RESULT_JSON__"):
            result_line = line[len("__RESULT_JSON__"):]

    if result_line is None:
        raise SegmentationError(
            "sam2_worker.pyから結果が返されませんでした。"
            f"\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )

    result = json.loads(result_line)
    if not result.get("ok", False):
        raise SegmentationError(
            f"sam2_worker.pyがエラーを返しました: {result.get('error')}\n{result.get('traceback', '')}"
        )
    return result
