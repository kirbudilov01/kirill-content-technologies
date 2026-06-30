#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$LAB_DIR/output/jobs/postiz-demo"
SCREEN_DIR="$OUT_DIR/screens"
mkdir -p "$OUT_DIR"

AUDIO_FILE="${AUDIO_FILE:-$OUT_DIR/kirill-postiz-voice-short.wav}"
AVATAR_VIDEO="${AVATAR_VIDEO:-$OUT_DIR/wav2lip/avatar-input_voice_Easy-Wav2Lip.mp4}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/postiz-talking-avatar-short.mp4}"

if [[ ! -f "$AUDIO_FILE" ]]; then
  echo "Missing audio file: $AUDIO_FILE" >&2
  exit 1
fi
if [[ ! -f "$AVATAR_VIDEO" ]]; then
  echo "Missing avatar video: $AVATAR_VIDEO" >&2
  exit 1
fi
for shot in 01-github.png 02-site.png 03-docs.png; do
  if [[ ! -f "$SCREEN_DIR/$shot" ]]; then
    echo "Missing screenshot: $SCREEN_DIR/$shot" >&2
    exit 1
  fi
done

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
fi

BASE="$TMP_DIR/base.png"
TOP_CAPTION="$TMP_DIR/top-caption.png"
PUNCH="$TMP_DIR/punch.png"
SUB1="$TMP_DIR/sub1.png"
SUB2="$TMP_DIR/sub2.png"
SUB3="$TMP_DIR/sub3.png"
DEMO="$TMP_DIR/postiz-demo.mp4"

magick -size 1080x1920 xc:'#050505' "$BASE"

magick -background '#000000cc' -fill white -font "$FONT" -pointsize 34 \
  -gravity northwest -size 850x86 caption:'Postiz: open-source AI social scheduler.' \
  "PNG32:$TOP_CAPTION"

magick -size 980x130 xc:none \
  -fill white -font "$FONT" -pointsize 56 -gravity center \
  -annotate -155+0 'POSTIZ =' \
  -fill '#fff200' -annotate +185+0 'DISTRIBUTION' \
  "PNG32:$PUNCH"

magick -background transparent -fill white -font "$FONT" -pointsize 38 \
  -gravity northwest -size 950x115 caption:'Open-source scheduler for every social channel.' \
  "PNG32:$SUB1"

magick -background transparent -fill white -font "$FONT" -pointsize 38 \
  -gravity northwest -size 950x115 caption:'A Buffer-style tool with AI, analytics, teams, and API.' \
  "PNG32:$SUB2"

magick -background transparent -fill white -font "$FONT" -pointsize 38 \
  -gravity northwest -size 950x115 caption:'For AtlasRepo, this becomes the posting layer.' \
  "PNG32:$SUB3"

DURATION="$(ffprobe -v error -show_entries format=duration -of default=nokey=1:noprint_wrappers=1 "$AUDIO_FILE")"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -t 5.1 -i "$SCREEN_DIR/01-github.png" \
  -loop 1 -t 5.1 -i "$SCREEN_DIR/02-site.png" \
  -loop 1 -t 5.1 -i "$SCREEN_DIR/03-docs.png" \
  -filter_complex "[0:v]scale=1280:720,setsar=1[v0];[1:v]scale=1280:720,setsar=1[v1];[2:v]scale=1280:720,setsar=1[v2];[v0][v1][v2]concat=n=3:v=1:a=0,fps=30,format=yuv420p[v]" \
  -map "[v]" -t "$DURATION" -c:v libx264 -movflags +faststart "$DEMO"

ffmpeg -hide_banner -loglevel error -y \
  -loop 1 -framerate 30 -i "$BASE" \
  -stream_loop -1 -i "$DEMO" \
  -stream_loop -1 -i "$AVATAR_VIDEO" \
  -i "$TOP_CAPTION" \
  -i "$PUNCH" \
  -i "$SUB1" \
  -i "$SUB2" \
  -i "$SUB3" \
  -i "$AUDIO_FILE" \
  -filter_complex "\
    [1:v]scale=980:560:force_original_aspect_ratio=decrease,pad=980:560:(ow-iw)/2:(oh-ih)/2:color=111111,setsar=1[demo];\
    [2:v]fps=30,scale=860:-1,crop=860:620:(iw-860)/2:210,setsar=1[face];\
    [0:v][demo]overlay=50:210[v1];\
    [v1][3:v]overlay=115:155[v2];\
    [v2][4:v]overlay=60:835[v3];\
    [v3][face]overlay=110:1035[v4];\
    [v4][5:v]overlay=60:1690:enable='between(t,0,5.2)'[v5];\
    [v5][6:v]overlay=60:1690:enable='between(t,5.2,10.4)'[v6];\
    [v6][7:v]overlay=60:1690:enable='gte(t,10.4)'[v]" \
  -map "[v]" -map 8:a \
  -t "$DURATION" \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -b:a 160k -movflags +faststart \
  "$OUT_FILE"

echo "Generated: $OUT_FILE"
