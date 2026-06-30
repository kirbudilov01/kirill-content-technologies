#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
ASSETS_DIR="$LAB_DIR/assets"
OUTPUT_DIR="$LAB_DIR/output"

SCRIPT_FILE="${SCRIPT_FILE:-$ASSETS_DIR/sample-short.txt}"
VOICE="${VOICE:-Daniel}"
TITLE="${TITLE:-AI Agent Demo}"
CTA="${CTA:-Full workflow packs live inside AtlasRepo}"
OUT_FILE="${OUT_FILE:-$OUTPUT_DIR/atlasrepo-split-short.mp4}"
AVATAR_FILE="${AVATAR_FILE:-$ASSETS_DIR/avatar.png}"
DEMO_FILE="${DEMO_FILE:-}"
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
BASE="$TMP_DIR/base.png"
AVATAR_TMP="$TMP_DIR/avatar.png"
CTA_IMG="$TMP_DIR/cta.png"
TITLE_IMG="$TMP_DIR/title.png"
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
  magick "$AVATAR_FILE" -resize 500x500^ -gravity center -extent 500x500 "$AVATAR_TMP"
else
  magick -size 500x500 xc:'#111827' \
    -fill '#7dd3fc' -font "$FONT" -pointsize 44 -gravity center \
    -annotate 0 'AVATAR' "$AVATAR_TMP"
fi

magick -background transparent -fill '#ffffff' -font "$FONT" -pointsize 50 \
  -gravity northwest -size 390x135 caption:"$TITLE" "PNG32:$TITLE_IMG"

magick -background transparent -fill '#d1d5db' -font "$FONT" -pointsize 34 \
  -gravity northwest -size 390x210 caption:"$CTA" "PNG32:$CTA_IMG"

magick -size 920x770 xc:'#111827' \
  -fill '#7dd3fc' -font "$FONT" -pointsize 52 -gravity center \
  -annotate 0 'DEMO SLOT' "$DEMO_SLOT"

magick -size 1080x1920 gradient:'#0b1020-#111827' \
  -fill '#111827' -draw 'roundrectangle 60,70 1020,900 30,30' \
  "$DEMO_SLOT" -gravity northwest -geometry +80+100 -composite \
  -fill '#0f172a' -draw 'roundrectangle 60,950 1020,1720 30,30' \
  "$AVATAR_TMP" -gravity northwest -geometry +95+1030 -composite \
  "$TITLE_IMG" -geometry +600+1055 -composite \
  "$CTA_IMG" -geometry +600+1225 -composite \
  -fill '#7dd3fc' -font "$FONT" -pointsize 44 -gravity northwest \
  -annotate +95+1770 'atlasrepo.com' \
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
    -filter_complex "[1:v]scale=920:770:force_original_aspect_ratio=decrease,pad=920:770:(ow-iw)/2:(oh-ih)/2:color=111827,setsar=1[demo];[0:v][demo]overlay=80:100[v]" \
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
