#!/usr/bin/env bash
# KymoTip同梱用のsam2環境(macOS Apple Silicon)を作成する。
#
# 出力先ディレクトリは、Windows版の packaging/envs/sam2 に相当する。
# venvはシステムのPythonへのシンボリックリンクを含み再配置できないため、
# 再配置可能なPython(python-build-standalone、uv経由)を丸ごとコピーして使う。
# 配置: <出力先>/bin/python3, <出力先>/lib/python3.11/site-packages,
#       <出力先>/sam2/weights/sam2_hiera_tiny.pt
#
# 使い方: packaging/macos/build_sam2_env.sh <出力先ディレクトリ>
# 前提: uvがPATHにあること。
set -euo pipefail

OUT="${1:?usage: build_sam2_env.sh <output-dir>}"
PY_VERSION="3.11"
# Windows版同梱環境(torch 2.4.0 / torchvision 0.19.0 / samv2 0.0.4)に合わせる。
# numpy 2.xはtorch 2.4.0と組み合わせると不整合の恐れがあるため1.xに固定する。
CHECKPOINT_URL="https://dl.fbaipublicfiles.com/segment_anything_2/072824/sam2_hiera_tiny.pt"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

uv python install "$PY_VERSION" --install-dir "$WORK/py"
PYDIR="$(find "$WORK/py" -mindepth 1 -maxdepth 1 -type d -name 'cpython-*' | head -n 1)"
if [ -z "$PYDIR" ]; then
  echo "python-build-standalone のディレクトリが見つかりません" >&2
  exit 1
fi

rm -rf "$OUT"
cp -R "$PYDIR" "$OUT"

# python-build-standaloneはEXTERNALLY-MANAGEDを宣言しているため、
# 専用に複製した環境へ入れる目的で明示的に許可する。
SAM2_BUILD_CUDA=0 uv pip install \
  --python "$OUT/bin/python3" \
  --break-system-packages \
  "torch==2.4.0" "torchvision==0.19.0" \
  "numpy<2" "pillow" "scipy" "scikit-image" \
  "samv2==0.0.4"

mkdir -p "$OUT/sam2/weights"
curl -fL --retry 3 -o "$OUT/sam2/weights/sam2_hiera_tiny.pt" "$CHECKPOINT_URL"

# 取り込み確認(ここで失敗すればビルドを止める)
"$OUT/bin/python3" -c "import torch, sam2, scipy, skimage; print('torch', torch.__version__)"
