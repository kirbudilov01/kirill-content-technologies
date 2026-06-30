#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
MODELS_DIR="$LAB_DIR/models"
VENV_DIR="$LAB_DIR/.venv-kokoro"

mkdir -p "$MODELS_DIR"

if [[ ! -d "$VENV_DIR" ]]; then
  uv venv --python 3.12 "$VENV_DIR"
fi

uv pip install --python "$VENV_DIR/bin/python" kokoro-onnx soundfile

if [[ ! -f "$MODELS_DIR/kokoro-v1.0.onnx" ]]; then
  curl -L \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx" \
    -o "$MODELS_DIR/kokoro-v1.0.onnx"
fi

if [[ ! -f "$MODELS_DIR/voices-v1.0.bin" ]]; then
  curl -L \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin" \
    -o "$MODELS_DIR/voices-v1.0.bin"
fi

echo "Kokoro is ready."
echo "Test:"
echo "$VENV_DIR/bin/python $LAB_DIR/scripts/kokoro_tts.py --text-file $LAB_DIR/assets/sample-short.txt --out $LAB_DIR/output/kokoro.wav"
