#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$LAB_DIR/output/jobs/postiz-demo"
SCREEN_DIR="$OUT_DIR/screens"
mkdir -p "$OUT_DIR"

AUDIO_FILE="${AUDIO_FILE:-$OUT_DIR/postiz-clean-kokoro.wav}"
AVATAR_VIDEO="${AVATAR_VIDEO:-$OUT_DIR/wav2lip-clean/avatar-input_voice_Easy-Wav2Lip.mp4}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/postiz-v2-clean-layout.mp4}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
fi

BASE="$TMP_DIR/base.png"
DEMO="$TMP_DIR/demo.mp4"
PUNCH="$TMP_DIR/punch.png"
SUB1="$TMP_DIR/sub1.png"
SUB2="$TMP_DIR/sub2.png"
SUB3="$TMP_DIR/sub3.png"

magick -size 1080x1920 xc:'#050505' "$BASE"

magick -size 980x125 xc:none \
  -fill white -font "$FONT" -pointsize 54 -gravity center \
  -annotate -170+0 'POSTIZ' \
  -fill '#fff200' -annotate +145+0 'AUTOPILOT' \
  "PNG32:$PUNCH"

magick -background transparent -fill white -font "$FONT" -pointsize 42 \
  -gravity center -size 980x120 caption:'Open-source scheduler for every social channel' \
  "PNG32:$SUB1"

magick -background transparent -fill white -font "$FONT" -pointsize 42 \
  -gravity center -size 980x120 caption:'AI content is useless without distribution' \
  "PNG32:$SUB2"

magick -background transparent -fill white -font "$FONT" -pointsize 42 \
  -gravity center -size 980x120 caption:'This can become AtlasRepo posting infrastructure' \
  "PNG32:$SUB3"

DURATION="$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$AUDIO_FILE")"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -t 3.1 -i "$SCREEN_DIR/01-github.png" \
  -loop 1 -t 3.0 -i "$SCREEN_DIR/02-site.png" \
  -loop 1 -t 3.0 -i "$SCREEN_DIR/03-docs.png" \
  -filter_complex "[0:v]scale=1280:720,setsar=1[v0];[1:v]scale=1280:720,setsar=1[v1];[2:v]scale=1280:720,setsar=1[v2];[v0][v1][v2]concat=n=3:v=1:a=0,fps=30,format=yuv420p[v]" \
  -map "[v]" -t "$DURATION" -c:v libx264 -movflags +faststart "$DEMO"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 30 -i "$BASE" \
  -stream_loop -1 -i "$DEMO" \
  -stream_loop -1 -i "$AVATAR_VIDEO" \
  -i "$PUNCH" \
  -i "$SUB1" \
  -i "$SUB2" \
  -i "$SUB3" \
  -i "$AUDIO_FILE" \
  -filter_complex "\
    [1:v]scale=980:555:force_original_aspect_ratio=decrease,pad=980:555:(ow-iw)/2:(oh-ih)/2:color=111111,setsar=1[demo];\
    [2:v]fps=30,scale=900:-1,crop=900:650:(iw-900)/2:165,setsar=1[face];\
    [0:v][demo]overlay=50:135[v1];\
    [v1][3:v]overlay=50:790[v2];\
    [v2][4:v]overlay=50:905:enable='between(t,0,3.2)'[v3];\
    [v3][5:v]overlay=50:905:enable='between(t,3.2,6.4)'[v4];\
    [v4][6:v]overlay=50:905:enable='gte(t,6.4)'[v5];\
    [v5][face]overlay=90:1125[v]" \
  -map "[v]" -map 7:a \
  -t "$DURATION" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT_FILE"

echo "Generated: $OUT_FILE"
