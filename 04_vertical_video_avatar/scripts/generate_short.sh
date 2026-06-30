#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
ASSETS_DIR="$LAB_DIR/assets"
OUTPUT_DIR="$LAB_DIR/output"

SCRIPT_FILE="${SCRIPT_FILE:-$ASSETS_DIR/sample-short.txt}"
VOICE="${VOICE:-Daniel}"
TITLE="${TITLE:-AI Agent Workflow}"
CTA="${CTA:-AtlasRepo tracks AI agents and turns them into workflow packs}"
OUT_FILE="${OUT_FILE:-$OUTPUT_DIR/atlasrepo-short.mp4}"
AVATAR_FILE="${AVATAR_FILE:-$ASSETS_DIR/avatar.png}"
AUDIO_FILE="${AUDIO_FILE:-}"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$SCRIPT_FILE" ]]; then
  echo "Missing script file: $SCRIPT_FILE" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

AUDIO_AIFF="$TMP_DIR/voice.aiff"
AUDIO_M4A="$TMP_DIR/voice.m4a"
POSTER="$TMP_DIR/poster.png"
AVATAR_TMP="$TMP_DIR/avatar.png"
CTA_IMG="$TMP_DIR/cta.png"

if [[ -n "$AUDIO_FILE" ]]; then
  if [[ ! -f "$AUDIO_FILE" ]]; then
    echo "Missing audio file: $AUDIO_FILE" >&2
    exit 1
  fi
  ffmpeg -hide_banner -loglevel error -y -i "$AUDIO_FILE" -c:a aac -b:a 160k "$AUDIO_M4A"
else
  say -v "$VOICE" -f "$SCRIPT_FILE" -o "$AUDIO_AIFF"
  ffmpeg -hide_banner -loglevel error -y -i "$AUDIO_AIFF" -c:a aac -b:a 160k "$AUDIO_M4A"
fi

DURATION="$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$AUDIO_M4A")"
FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Supplemental/Helvetica.ttf"
fi

if [[ -f "$AVATAR_FILE" ]]; then
  magick "$AVATAR_FILE" -resize 760x760^ -gravity center -extent 760x760 "$AVATAR_TMP"
else
  magick -size 760x760 xc:'#111827' \
    -fill '#7dd3fc' -font "$FONT" -pointsize 58 -gravity center \
    -annotate 0 'AVATAR SLOT' "$AVATAR_TMP"
fi

magick -background transparent -fill '#d1d5db' -font "$FONT" -pointsize 40 \
  -gravity northwest -size 850x210 caption:"$CTA" "PNG32:$CTA_IMG"

magick -size 1080x1920 gradient:'#0b1020-#111827' \
  -fill '#111827' -draw 'roundrectangle 90,190 990,1040 34,34' \
  "$AVATAR_TMP" -gravity north -geometry +0+235 -composite \
  -fill '#0f172a' -draw 'roundrectangle 90,1120 990,1560 34,34' \
  -fill '#ffffff' -font "$FONT" -pointsize 68 -gravity northwest \
  -annotate +110+1160 "$TITLE" \
  "$CTA_IMG" -geometry +110+1305 -composite \
  -fill '#7dd3fc' -font "$FONT" -pointsize 48 -gravity northwest \
  -annotate +110+1760 'atlasrepo.com' \
  "$POSTER"

if [[ -f "$AVATAR_FILE" ]]; then
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "$POSTER" \
    -i "$AUDIO_M4A" \
    -map 0:v -map 1:a \
    -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k "$OUT_FILE"
else
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "$POSTER" \
    -i "$AUDIO_M4A" \
    -map 0:v -map 1:a \
    -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k "$OUT_FILE"
fi

echo "Generated: $OUT_FILE"
