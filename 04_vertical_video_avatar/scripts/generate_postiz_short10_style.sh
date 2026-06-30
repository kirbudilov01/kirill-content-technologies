#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$LAB_DIR/output/jobs/postiz-demo"
SCREEN_DIR="$OUT_DIR/screens"
mkdir -p "$OUT_DIR"

AUDIO_FILE="${AUDIO_FILE:-$OUT_DIR/postiz-short10-liam.wav}"
AVATAR_VIDEO="${AVATAR_VIDEO:-$OUT_DIR/wav2lip-short10/avatar-input_voice_Easy-Wav2Lip.mp4}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/postiz-short10-style-v3.mp4}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
fi

BASE="$TMP_DIR/base.png"
DEMO="$TMP_DIR/demo.mp4"

make_caption() {
  local key="$1"
  local line="$2"
  local out="$3"
  local key_img="$TMP_DIR/key-$(basename "$out").png"
  local line_img="$TMP_DIR/line-$(basename "$out").png"

  magick -background transparent -fill '#fff200' -font "$FONT" -pointsize 76 \
    -gravity center -size 980x88 caption:"$key" "PNG32:$key_img"
  magick -background transparent -fill white -font "$FONT" -pointsize 42 \
    -gravity center -size 980x104 caption:"$line" "PNG32:$line_img"
  magick -size 980x210 xc:none "$key_img" -gravity north -geometry +0+0 -composite \
    "$line_img" -gravity north -geometry +0+96 -composite "PNG32:$out"
}

magick -size 1080x1920 xc:'#050505' "$BASE"

make_caption "DID YOU KNOW?" "Stop posting the same content everywhere by hand" "$TMP_DIR/sub1.png"
make_caption "POSTIZ" "Open-source social media scheduling" "$TMP_DIR/sub2.png"
make_caption "PLAN + SCHEDULE" "Turn finished content into a real queue" "$TMP_DIR/sub3.png"
make_caption "CALENDAR" "Composer, queue, channels, publishing flow" "$TMP_DIR/sub4.png"
make_caption "VISIBILITY" "The boring layer that decides if people see it" "$TMP_DIR/sub5.png"
make_caption "OPEN SOURCE" "Would you replace a paid scheduler with this?" "$TMP_DIR/sub6.png"
make_caption "ATLASREPO" "More tools like this in the channel header" "$TMP_DIR/sub7.png"

DURATION="$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$AUDIO_FILE")"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -t 7.4 -i "$SCREEN_DIR/01-github.png" \
  -loop 1 -t 7.4 -i "$SCREEN_DIR/02-site.png" \
  -loop 1 -t 7.4 -i "$SCREEN_DIR/03-docs.png" \
  -filter_complex "[0:v]scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608,setsar=1[v0];[1:v]scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608,setsar=1[v1];[2:v]scale=1080:608:force_original_aspect_ratio=increase,crop=1080:608,setsar=1[v2];[v0][v1][v2]concat=n=3:v=1:a=0,fps=30,format=yuv420p[v]" \
  -map "[v]" -t "$DURATION" -c:v libx264 -movflags +faststart "$DEMO"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 30 -i "$BASE" \
  -stream_loop -1 -i "$DEMO" \
  -stream_loop -1 -i "$AVATAR_VIDEO" \
  -i "$TMP_DIR/sub1.png" \
  -i "$TMP_DIR/sub2.png" \
  -i "$TMP_DIR/sub3.png" \
  -i "$TMP_DIR/sub4.png" \
  -i "$TMP_DIR/sub5.png" \
  -i "$TMP_DIR/sub6.png" \
  -i "$TMP_DIR/sub7.png" \
  -i "$AUDIO_FILE" \
  -filter_complex "\
    [2:v]fps=30,scale=700:-1,crop=700:640:(iw-700)/2:125,setsar=1[face];\
    [0:v][1:v]overlay=0:70[v1];\
    [v1][3:v]overlay=50:705:enable='between(t,0,3.2)'[v2];\
    [v2][4:v]overlay=50:705:enable='between(t,3.2,6.4)'[v3];\
    [v3][5:v]overlay=50:705:enable='between(t,6.4,9.6)'[v4];\
    [v4][6:v]overlay=50:705:enable='between(t,9.6,12.8)'[v5];\
    [v5][7:v]overlay=50:705:enable='between(t,12.8,16.0)'[v6];\
    [v6][8:v]overlay=50:705:enable='between(t,16.0,19.2)'[v7];\
    [v7][9:v]overlay=50:705:enable='gte(t,19.2)'[v8];\
    [v8][face]overlay=190:1210[v]" \
  -map "[v]" -map 10:a \
  -t "$DURATION" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT_FILE"

echo "Generated: $OUT_FILE"
