#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
ASSETS_DIR="$LAB_DIR/assets"
OUTPUT_DIR="$LAB_DIR/output"

SCRIPT_FILE="${SCRIPT_FILE:-$ASSETS_DIR/sample-short.txt}"
VOICE="${VOICE:-Daniel}"
OUT_FILE="${OUT_FILE:-$OUTPUT_DIR/atlasrepo-reference-short.mp4}"
AVATAR_FILE="${AVATAR_FILE:-$ASSETS_DIR/avatar.png}"
DEMO_FILE="${DEMO_FILE:-}"
AUDIO_FILE="${AUDIO_FILE:-}"
TOP_TEXT="${TOP_TEXT:-New AI agent update looks small, but the workflow is completely different.}"
PUNCH_LEFT="${PUNCH_LEFT:-UPDATE IS}"
PUNCH_RIGHT="${PUNCH_RIGHT:-INSANE}"
HANDLE="${HANDLE:-@AtlasRepo}"
BUTTON_TEXT="${BUTTON_TEXT:-Follow}"
VIDEO_TITLE="${VIDEO_TITLE:-AI agents are becoming workflow builders.}"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$SCRIPT_FILE" ]]; then
  echo "Missing script file: $SCRIPT_FILE" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

AUDIO_AIFF="$TMP_DIR/voice.aiff"
AUDIO_M4A="$TMP_DIR/voice.m4a"
BASE="$TMP_DIR/base.png"
AVATAR_CARD="$TMP_DIR/avatar-card.png"
AVATAR_TMP="$TMP_DIR/avatar.png"
TOP_TEXT_IMG="$TMP_DIR/top-text.png"
TITLE_IMG="$TMP_DIR/title.png"
PUNCH_IMG="$TMP_DIR/punch.png"
DEMO_SLOT="$TMP_DIR/demo-slot.png"

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
  magick "$AVATAR_FILE" -resize 760x500 -background '#111827' -gravity center -extent 760x500 "$AVATAR_TMP"
else
  magick -size 820x520 xc:'#111827' \
    -fill '#7dd3fc' -font "$FONT" -pointsize 52 -gravity center \
    -annotate 0 'AVATAR' "$AVATAR_TMP"
fi

magick -size 930x500 xc:none \
  -fill '#111827' -draw 'roundrectangle 0,0 930,500 36,36' \
  "$AVATAR_TMP" -gravity center -composite \
  "$AVATAR_CARD"

magick -background '#00000099' -fill '#ffffff' -font "$FONT" -pointsize 34 \
  -gravity northwest -size 770x90 caption:"$TOP_TEXT" "PNG32:$TOP_TEXT_IMG"

magick -background transparent -fill '#ffffff' -font "$FONT" -pointsize 40 \
  -gravity northwest -size 850x110 caption:"▶ $VIDEO_TITLE" "PNG32:$TITLE_IMG"

magick -background transparent \
  -font "$FONT" -pointsize 64 -gravity center \
  -fill '#ffffff' label:"$PUNCH_LEFT " \
  -fill '#f7e018' label:"$PUNCH_RIGHT" \
  +append "PNG32:$PUNCH_IMG"

magick -size 980x560 xc:'#e5e7eb' \
  -fill '#111827' -font "$FONT" -pointsize 52 -gravity center \
  -annotate 0 'DEMO / REPO / APP' "$DEMO_SLOT"

magick -size 1080x1920 xc:'#000000' \
  -fill '#0b0b0b' -draw 'roundrectangle 0,0 1080,1920 28,28' \
  "$DEMO_SLOT" -gravity northwest -geometry +50+280 -composite \
  "$TOP_TEXT_IMG" -gravity northwest -geometry +235+205 -composite \
  "$PUNCH_IMG" -gravity northwest -geometry +295+940 -composite \
  "$AVATAR_CARD" -gravity northwest -geometry +75+1110 -composite \
  -fill '#ffffff' -font "$FONT" -pointsize 34 -gravity northwest \
  -annotate +115+1245 "$HANDLE" \
  -fill '#ffffff' -draw 'roundrectangle 710,1135 945,1210 38,38' \
  -fill '#111827' -font "$FONT" -pointsize 30 -gravity northwest \
  -annotate +746+1180 "$BUTTON_TEXT" \
  -fill '#ffffff' -font "$FONT" -pointsize 36 -gravity northwest \
  -annotate +50+1695 "$VIDEO_TITLE" \
  "$BASE"

if [[ -n "$DEMO_FILE" ]]; then
  if [[ ! -f "$DEMO_FILE" ]]; then
    echo "Missing demo file: $DEMO_FILE" >&2
    exit 1
  fi

  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "$BASE" \
    -stream_loop -1 -i "$DEMO_FILE" \
    -i "$AUDIO_M4A" \
    -filter_complex "[1:v]scale=980:560:force_original_aspect_ratio=decrease,pad=980:560:(ow-iw)/2:(oh-ih)/2:color=e5e7eb,setsar=1[demo];[0:v][demo]overlay=50:280[v]" \
    -map "[v]" -map 2:a \
    -t "$DURATION" -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k "$OUT_FILE"
else
  ffmpeg -hide_banner -loglevel error -y \
    -loop 1 -framerate 30 -i "$BASE" \
    -i "$AUDIO_M4A" \
    -map 0:v -map 1:a \
    -shortest -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k "$OUT_FILE"
fi

echo "Generated: $OUT_FILE"
