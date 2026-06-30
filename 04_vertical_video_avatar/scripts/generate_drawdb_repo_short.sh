#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$LAB_DIR/output/jobs/drawdb-demo"
mkdir -p "$OUT_DIR"

DEMO_FILE="${DEMO_FILE:-$OUT_DIR/drawdb-local-skill-walkthrough-20260630-235002.mov}"
SCRIPT_FILE="${SCRIPT_FILE:-$LAB_DIR/assets/drawdb-short-script.txt}"
AUDIO_FILE="${AUDIO_FILE:-$OUT_DIR/drawdb-short-voice.wav}"
BASE_FILE="${BASE_FILE:-$OUT_DIR/drawdb-short-v3-base.mp4}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/drawdb-short-v3-final.mp4}"
VOICE="${VOICE:-am_liam}"
SPEED="${SPEED:-1.08}"
DEMO_START="${DEMO_START:-0}"

if [[ ! -f "$DEMO_FILE" ]]; then
  echo "Missing demo file: $DEMO_FILE" >&2
  exit 1
fi
if [[ ! -f "$SCRIPT_FILE" ]]; then
  echo "Missing script file: $SCRIPT_FILE" >&2
  exit 1
fi

FONT_BOLD="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_REG="/System/Library/Fonts/Supplemental/Arial.ttf"
if [[ ! -f "$FONT_BOLD" ]]; then
  FONT_BOLD="$FONT_REG"
fi

if [[ ! -f "$AUDIO_FILE" ]]; then
  "$LAB_DIR/.venv-kokoro/bin/python" "$LAB_DIR/scripts/kokoro_tts.py" \
    --text-file "$SCRIPT_FILE" \
    --out "$AUDIO_FILE" \
    --voice "$VOICE" \
    --speed "$SPEED"
fi

DURATION="$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$AUDIO_FILE")"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

TOP_TAG="$TMP_DIR/top-tag.png"
PUNCH="$TMP_DIR/punch.png"
SUB_NOTE="$TMP_DIR/sub-note.png"
CAP1="$TMP_DIR/cap1.png"
CAP2="$TMP_DIR/cap2.png"
CAP3="$TMP_DIR/cap3.png"
CTA="$TMP_DIR/cta.png"

magick -size 420x64 xc:none \
  -fill '#111111ee' -draw 'roundrectangle 0,0 420,64 18,18' \
  -fill '#14f1b2' -draw 'roundrectangle 18,21 38,42 10,10' \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 29 -gravity center \
  -annotate +18+0 '38K+ STAR REPO' \
  "PNG32:$TOP_TAG"

magick -size 1000x148 xc:none \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 58 -gravity center \
  -stroke '#000000' -strokewidth 4 -annotate +0-34 'DESIGN DATABASES' \
  -stroke none -fill '#ffffff' -annotate +0-34 'DESIGN DATABASES' \
  -stroke '#000000' -strokewidth 4 -fill '#fff200' -annotate +0+38 'VISUALLY' \
  -stroke none -fill '#fff200' -annotate +0+38 'VISUALLY' \
  "PNG32:$PUNCH"

magick -size 900x62 xc:none \
  -fill '#d8d8d8' -font "$FONT_REG" -pointsize 30 -gravity center \
  -annotate +0+0 'Take the power from GitHub to your workflow' \
  "PNG32:$SUB_NOTE"

magick -size 1000x210 xc:none \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 64 -gravity center \
  -stroke '#000000' -strokewidth 5 -annotate +0-38 'VISUAL DATABASE' \
  -stroke none -fill '#ffffff' -annotate +0-38 'VISUAL DATABASE' \
  -stroke '#000000' -strokewidth 5 -fill '#fff200' -annotate +0+42 'DESIGN' \
  -stroke none -fill '#fff200' -annotate +0+42 'DESIGN' \
  "PNG32:$CAP1"

magick -size 1000x210 xc:none \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 64 -gravity center \
  -stroke '#000000' -strokewidth 5 -annotate +0-38 'EXPORT SQL' \
  -stroke none -fill '#ffffff' -annotate +0-38 'EXPORT SQL' \
  -stroke '#000000' -strokewidth 5 -fill '#fff200' -annotate +0+42 'IN SECONDS' \
  -stroke none -fill '#fff200' -annotate +0+42 'IN SECONDS' \
  "PNG32:$CAP2"

magick -size 1000x210 xc:none \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 64 -gravity center \
  -stroke '#000000' -strokewidth 5 -annotate +0-38 'RUN IT LOCALLY' \
  -stroke none -fill '#ffffff' -annotate +0-38 'RUN IT LOCALLY' \
  -stroke '#000000' -strokewidth 5 -fill '#14f1b2' -annotate +0+42 'FOR FREE' \
  -stroke none -fill '#14f1b2' -annotate +0+42 'FOR FREE' \
  "PNG32:$CAP3"

magick -size 920x156 xc:none \
  -fill '#ffffff' -draw 'roundrectangle 0,0 920,156 34,34' \
  -fill '#080808' -draw 'roundrectangle 14,14 906,142 26,26' \
  -fill '#14f1b2' -draw 'roundrectangle 38,38 410,84 23,23' \
  -fill '#050505' -font "$FONT_BOLD" -pointsize 26 -gravity northwest \
  -annotate +62+45 'OPEN SOURCE REPO' \
  -fill '#fff200' -font "$FONT_BOLD" -pointsize 52 -gravity northwest \
  -annotate +466+47 'atlasrepo.com' \
  -fill '#ffffff' -font "$FONT_REG" -pointsize 26 -gravity northwest \
  -annotate +68+104 'Find useful repos before they become obvious.' \
  "PNG32:$CTA"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=#050505:s=1080x1920:r=30:d=$DURATION" \
  -ss "$DEMO_START" -i "$DEMO_FILE" \
  -i "$TOP_TAG" \
  -i "$PUNCH" \
  -i "$SUB_NOTE" \
  -i "$CAP1" \
  -i "$CAP2" \
  -i "$CAP3" \
  -i "$CTA" \
  -i "$AUDIO_FILE" \
  -filter_complex "\
    [1:v]fps=30,crop=1136:710:345:34,scale=1000:625,setsar=1[demo];\
    [0:v]drawbox=x=36:y=78:w=1008:h=633:color=#ffffff@0.16:t=4,drawbox=x=44:y=86:w=992:h=617:color=#111111@1:t=10[bg0];\
    [bg0][demo]overlay=40:90[v1];\
    [v1][2:v]overlay=72:38[v2];\
    [v2][3:v]overlay=(main_w-overlay_w)/2:755[v3];\
    [v3][4:v]overlay=(main_w-overlay_w)/2:908[v4];\
    [v4][5:v]overlay=(main_w-overlay_w)/2:1085:enable='lt(t,3.6)'[v5];\
    [v5][6:v]overlay=(main_w-overlay_w)/2:1085:enable='between(t,3.6,7.2)'[v6];\
    [v6][7:v]overlay=(main_w-overlay_w)/2:1085:enable='gte(t,7.2)'[v7];\
    [v7][8:v]overlay=(main_w-overlay_w)/2:1580[v]" \
  -map "[v]" -map 9:a \
  -t "$DURATION" \
  -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p \
  -c:a aac -b:a 160k -movflags +faststart \
  "$OUT_FILE"

PREVIEW="${OUT_FILE%.mp4}-preview.png"
ffmpeg -hide_banner -loglevel error -y -ss 3.0 -i "$OUT_FILE" -frames:v 1 "$PREVIEW"

echo "Generated: $OUT_FILE"
echo "Preview: $PREVIEW"
