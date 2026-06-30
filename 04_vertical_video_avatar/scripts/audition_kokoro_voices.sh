#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
OUT_DIR="$LAB_DIR/output/voice-auditions"
TEXT_FILE="${TEXT_FILE:-$LAB_DIR/assets/voice-audition.txt}"
VOICES="${VOICES:-am_liam am_michael am_onyx am_eric bm_lewis bm_daniel af_sarah af_nova af_bella}"
SPEED="${SPEED:-1.0}"

mkdir -p "$OUT_DIR"

for voice in $VOICES; do
  echo "Generating $voice..."
  "$LAB_DIR/.venv-kokoro/bin/python" "$LAB_DIR/scripts/kokoro_tts.py" \
    --text-file "$TEXT_FILE" \
    --out "$OUT_DIR/$voice.wav" \
    --voice "$voice" \
    --speed "$SPEED"
done

echo "Generated voice auditions in: $OUT_DIR"

