"""バックグラウンドスレッドで任意のcallableを実行する共通ワーカー。

各ステージの実行ボタンはこれ経由でcore/segmentationの関数を呼ぶことで、
処理中もUIスレッドをブロックしない。
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal


class FunctionWorker(QObject):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, func: Callable[[], Any]) -> None:
        super().__init__()
        self._func = func

    def run(self) -> None:
        try:
            result = self._func()
        except Exception as exc:  # ワーカースレッドの例外はシグナル経由でUIスレッドへ伝える
            self.error.emit(str(exc))
            return
        self.finished.emit(result)


def run_in_background(
    func: Callable[[], Any],
    on_finished: Callable[[Any], None],
    on_error: Callable[[str], None],
) -> tuple[QThread, FunctionWorker]:
    """funcを別スレッドで実行し、完了/エラーをコールバックする。

    呼び出し元は戻り値の (thread, worker) を、GCされないようインスタンス変数として
    保持し続ける必要がある。
    """
    thread = QThread()
    worker = FunctionWorker(func)
    worker.moveToThread(thread)

    thread.started.connect(worker.run)
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    worker.finished.connect(thread.quit)
    worker.error.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    worker.error.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)

    thread.start()
    return thread, worker
