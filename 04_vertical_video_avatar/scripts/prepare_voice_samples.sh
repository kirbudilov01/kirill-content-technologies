#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
RAW_DIR="$LAB_DIR/identity/voice/raw"
PROCESSED_DIR="$LAB_DIR/identity/voice/processed"

mkdir -p "$RAW_DIR" "$PROCESSED_DIR"

shopt -s nullglob
files=("$RAW_DIR"/*)

if [[ ${#files[@]} -eq 0 ]]; then
  echo "No voice files found in: $RAW_DIR"
  echo "Put .wav, .m4a, or .mp3 files there first."
  exit 0
fi

index=1
for file in "${files[@]}"; do
  ext="${file##*.}"
  ext_lower="$(printf '%s' "$ext" | tr '[:upper:]' '[:lower:]')"
  case "$ext_lower" in
    wav|m4a|mp3|aac|flac)
      out="$PROCESSED_DIR/kirill_$(printf '%03d' "$index").wav"
      echo "Processing $file -> $out"
      ffmpeg -hide_banner -loglevel error -y \
        -i "$file" \
        -af "silenceremove=start_periods=1:start_duration=0.2:start_threshold=-45dB,loudnorm=I=-16:TP=-1.5:LRA=11" \
        -ar 24000 -ac 1 "$out"
      index=$((index + 1))
      ;;
    *)
      echo "Skipping unsupported file: $file"
      ;;
  esac
done

echo "Processed samples:"
ls -lh "$PROCESSED_DIR"
