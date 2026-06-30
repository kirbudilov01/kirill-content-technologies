#!/usr/bin/env bash
set -euo pipefail

LAB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$LAB_DIR/output/templates/repo-cta-short"
mkdir -p "$OUT_DIR"

DEMO_FILE="${DEMO_FILE:-$LAB_DIR/output/jobs/it-tools-demo/it-tools-screenshot-demo-8s.mp4}"
SCRIPT_FILE="${SCRIPT_FILE:-$LAB_DIR/assets/repo-cta-short-script.txt}"
AUDIO_FILE="${AUDIO_FILE:-$OUT_DIR/repo-cta-short-voice.wav}"
BASE_FILE="${BASE_FILE:-$OUT_DIR/repo-cta-short-base.mp4}"
OUT_FILE="${OUT_FILE:-$OUT_DIR/repo-cta-short-final.mp4}"
VOICE="${VOICE:-am_liam}"
SPEED="${SPEED:-1.08}"
HEADER_TEXT="${HEADER_TEXT:-ATLASREPO DEMO}"
BADGE_TEXT="${BADGE_TEXT:-THIS REPO SAVES DEV HOURS}"
CTA_LABEL="${CTA_LABEL:-OPEN-SOURCE REPO:}"
CTA_URL="${CTA_URL:-atlasrepo.com}"
TAGLINE_TEXT="${TAGLINE_TEXT:-Find it. Launch it. Turn it into a workflow.}"

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

TITLE_PNG="$TMP_DIR/title.png"
ACCENT_PNG="$TMP_DIR/accent.png"
BADGE_PNG="$TMP_DIR/badge.png"
CTA_PNG="$TMP_DIR/cta.png"
ARROW_PNG="$TMP_DIR/arrow.png"
URL_PNG="$TMP_DIR/url.png"
TAGLINE_PNG="$TMP_DIR/tagline.png"

magick -size 620x72 xc:none \
  -fill '#000000aa' -draw 'roundrectangle 0,0 620,72 18,18' \
  -fill '#14f1b2' -draw 'roundrectangle 0,0 10,72 5,5' \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 34 -gravity center \
  -annotate +12+0 "$HEADER_TEXT" "PNG32:$TITLE_PNG"

magick -size 992x18 xc:none \
  -fill '#14f1b2' -draw 'roundrectangle 0,0 596,18 9,9' \
  -fill '#fff200' -draw 'roundrectangle 616,0 992,18 9,9' \
  "PNG32:$ACCENT_PNG"

magick -size 840x82 xc:none \
  -fill '#111111' -stroke '#14f1b2' -strokewidth 3 -draw 'roundrectangle 2,2 838,80 26,26' \
  -stroke none -fill '#14f1b2' -font "$FONT_BOLD" -pointsize 36 -gravity center \
  -annotate +0+0 "$BADGE_TEXT" "PNG32:$BADGE_PNG"

magick -size 1020x86 xc:none \
  -fill '#ffffff' -font "$FONT_BOLD" -pointsize 58 -gravity center \
  -stroke '#000000' -strokewidth 4 -annotate +0+0 "$CTA_LABEL" \
  -stroke none -fill '#ffffff' -annotate +0+0 "$CTA_LABEL" "PNG32:$CTA_PNG"

magick -size 140x92 xc:none \
  -fill '#fff200' -font "$FONT_BOLD" -pointsize 76 -gravity center \
  -stroke '#000000' -strokewidth 4 -annotate +0-2 '↓' \
  -stroke none -fill '#fff200' -annotate +0-2 '↓' "PNG32:$ARROW_PNG"

magick -size 680x86 xc:none \
  -fill '#fff200' -font "$FONT_BOLD" -pointsize 54 -gravity center \
  -stroke '#000000' -strokewidth 4 -annotate +0+0 "$CTA_URL" \
  -stroke none -fill '#fff200' -annotate +0+0 "$CTA_URL" "PNG32:$URL_PNG"

magick -size 980x64 xc:none \
  -fill '#d7d7d7' -font "$FONT_REG" -pointsize 34 -gravity center \
  -stroke '#000000' -strokewidth 3 -annotate +0+0 "$TAGLINE_TEXT" \
  -stroke none -fill '#d7d7d7' -annotate +0+0 "$TAGLINE_TEXT" "PNG32:$TAGLINE_PNG"

ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "color=c=#050505:s=1080x1920:r=30:d=$DURATION" \
  -stream_loop -1 -i "$DEMO_FILE" \
  -i "$TITLE_PNG" \
  -i "$ACCENT_PNG" \
  -i "$BADGE_PNG" \
  -i "$CTA_PNG" \
  -i "$ARROW_PNG" \
  -i "$URL_PNG" \
  -i "$TAGLINE_PNG" \
  -i "$AUDIO_FILE" \
  -filter_complex "\
    [1:v]fps=30,scale=960:540:force_original_aspect_ratio=decrease,pad=960:540:(ow-iw)/2:(oh-ih)/2:color=#111111,setsar=1[demo];\
    [0:v]drawbox=x=44:y=116:w=992:h=572:color=#2f2f2f@1:t=4,drawbox=x=52:y=124:w=976:h=556:color=#0e0e0e@1:t=10[bg0];\
    [bg0][demo]overlay=60:132[v1];\
    [v1][2:v]overlay=60:54[v2];\
    [v2][3:v]overlay=44:690[v3];\
    [v3][4:v]overlay=(main_w-overlay_w)/2:1088[v4];\
    [v4][5:v]overlay=(main_w-overlay_w)/2:1268[v5];\
    [v5][6:v]overlay=(main_w-overlay_w)/2:1342[v6];\
    [v6][7:v]overlay=(main_w-overlay_w)/2:1434[v7];\
    [v7][8:v]overlay=(main_w-overlay_w)/2:1518[v]" \
  -map "[v]" -map 9:a \
  -t "$DURATION" \
  -c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p \
  -c:a aac -b:a 160k -movflags +faststart \
  "$BASE_FILE"

"$LAB_DIR/.venv-kokoro/bin/python" "$LAB_DIR/scripts/render_local_captions.py" \
  --video "$BASE_FILE" \
  --text-file "$SCRIPT_FILE" \
  --out "$OUT_FILE" \
  --fps 30 \
  --y-ratio 0.47

PREVIEW="${OUT_FILE%.mp4}-preview.png"
ffmpeg -hide_banner -loglevel error -y -ss 2.2 -i "$OUT_FILE" -frames:v 1 "$PREVIEW"

echo "Generated: $OUT_FILE"
echo "Preview: $PREVIEW"
