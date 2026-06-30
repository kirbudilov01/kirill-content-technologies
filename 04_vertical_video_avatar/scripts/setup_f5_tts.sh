#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
VENV_DIR="$LAB_DIR/.venv-f5"

if [[ ! -d "$VENV_DIR" ]]; then
  uv venv --python 3.12 "$VENV_DIR"
fi

uv pip install --python "$VENV_DIR/bin/python" torch torchaudio f5-tts soundfile

echo "F5-TTS environment is ready."
echo "Python: $VENV_DIR/bin/python"

