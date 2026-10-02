#!/usr/bin/env bash
# CI用ラッパー: 引数のコマンドを実行し、失敗時は出力末尾をGitHub Actionsの
# エラー注釈として書き出す(ジョブログは管理者認証が必要だが、注釈は
# 公開リポジトリならAPIから認証なしで読めるため、失敗原因の確認に使う)。
#
# 使い方: bash packaging/macos/ci_run.sh <タイトル> <コマンド> [引数...]
set -uo pipefail

TITLE="$1"
shift
LOG="$(mktemp)"

"$@" 2>&1 | tee "$LOG"
status=${PIPESTATUS[0]}

if [ "$status" -ne 0 ]; then
  # 注釈メッセージ内の改行は%0A、%は%25にエスケープする必要がある
  msg="$(tail -n 40 "$LOG" | sed 's/%/%25/g' | awk '{printf "%s%%0A", $0}')"
  echo "::error title=${TITLE} (exit ${status})::${msg}"
fi
rm -f "$LOG"
exit "$status"
