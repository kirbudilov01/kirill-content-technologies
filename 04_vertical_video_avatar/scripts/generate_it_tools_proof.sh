#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$LAB_DIR/output/jobs/it-tools-demo"
mkdir -p "$OUT_DIR"

DEMO_FILE="${DEMO_FILE:-/Users/kirill/Movies/Codex Screencasts/it-tools-local-demo-20260627-092342.mov}"
AVATAR_VIDEO="${AVATAR_VIDEO:-/Users/kirill/Downloads/ABOUT TELEGRAM MINI APPS.mp4}"
AUDIO_FILE="${AUDIO_FILE:-$OUT_DIR/kirill-it-tools-voice-short.wav}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/it-tools-proof-master.mp4}"
AVATAR_START="${AVATAR_START:-8}"
DEMO_START="${DEMO_START:-0}"

if [[ ! -f "$DEMO_FILE" ]]; then
  echo "Missing demo file: $DEMO_FILE" >&2
  exit 1
fi
if [[ ! -f "$AVATAR_VIDEO" ]]; then
  echo "Missing avatar video: $AVATAR_VIDEO" >&2
  exit 1
fi
if [[ ! -f "$AUDIO_FILE" ]]; then
  echo "Missing audio file: $AUDIO_FILE" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
fi

BASE="$TMP_DIR/base.png"
TOP_CAPTION="$TMP_DIR/top-caption.png"
PUNCH="$TMP_DIR/punch.png"
BOTTOM_TITLE="$TMP_DIR/bottom-title.png"

magick -size 1080x1920 xc:'#050505' "$BASE"

magick -background '#000000cc' -fill white -font "$FONT" -pointsize 34 \
  -gravity northwest -size 850x86 caption:'Open-source dev toolbox you can run locally.' \
  "PNG32:$TOP_CAPTION"

magick -size 920x130 xc:none \
  -fill white -font "$FONT" -pointsize 58 -gravity center \
  -annotate -130+0 'REPO TO' \
  -fill '#fff200' -annotate +155+0 'CONTENT' \
  "PNG32:$PUNCH"

magick -background transparent -fill white -font "$FONT" -pointsize 36 \
  -gravity northwest -size 960x115 caption:'▶ AtlasRepo should find it, launch it, record it, and turn it into a workflow.' \
  "PNG32:$BOTTOM_TITLE"

DURATION="$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$AUDIO_FILE")"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 30 -i "$BASE" \
  -stream_loop -1 -ss "$DEMO_START" -i "$DEMO_FILE" \
  -stream_loop -1 -ss "$AVATAR_START" -i "$AVATAR_VIDEO" \
  -i "$TOP_CAPTION" \
  -i "$PUNCH" \
  -i "$BOTTOM_TITLE" \
  -i "$AUDIO_FILE" \
  -filter_complex "\
    [1:v]scale=980:560:force_original_aspect_ratio=decrease,pad=980:560:(ow-iw)/2:(oh-ih)/2:color=111111,setsar=1[demo];\
    [2:v]fps=30,scale=860:-1,crop=860:620:(iw-860)/2:300,setsar=1[face];\
    [0:v][demo]overlay=50:210[v1];\
    [v1][3:v]overlay=115:155[v2];\
    [v2][4:v]overlay=80:835[v3];\
    [v3][face]overlay=110:1035[v4];\
    [v4][5:v]overlay=60:1690[v]" \
  -map "[v]" -map 6:a \
  -t "$DURATION" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT_FILE"

echo "Generated: $OUT_FILE"
