#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
LAB_DIR="$ROOT_DIR/research/avatar-lab"
ASSETS_DIR="$LAB_DIR/assets"
OUTPUT_DIR="$LAB_DIR/output/thumbnails"

FACE_FILE="${FACE_FILE:-$ASSETS_DIR/avatar.png}"
OUT_FILE="${OUT_FILE:-$OUTPUT_DIR/thumbnail.png}"
STYLE="${STYLE:-green}"
TOP_TEXT="${TOP_TEXT:-NEW & FREE}"
BADGE_TEXT="${BADGE_TEXT:-AI AGENT}"
BOTTOM_TEXT="${BOTTOM_TEXT:-RUNS LOCAL}"

mkdir -p "$OUTPUT_DIR"

if [[ ! -f "$FACE_FILE" ]]; then
  echo "Missing face file: $FACE_FILE" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

FONT="/System/Library/Fonts/Supplemental/Arial Bold.ttf"
if [[ ! -f "$FONT" ]]; then
  FONT="/System/Library/Fonts/Supplemental/Arial.ttf"
fi

FACE="$TMP_DIR/face.png"
BADGE="$TMP_DIR/badge.png"
BG="$TMP_DIR/bg.png"

case "$STYLE" in
  green)
    BG_A="#020617"
    BG_B="#052e16"
    ACCENT="#39ff14"
    HILITE="#ccff00"
    ;;
  red)
    BG_A="#0b0202"
    BG_B="#7f1d1d"
    ACCENT="#ff3131"
    HILITE="#ffffff"
    ;;
  orange)
    BG_A="#050505"
    BG_B="#7c2d12"
    ACCENT="#ff7a18"
    HILITE="#ffffff"
    ;;
  white)
    BG_A="#ffffff"
    BG_B="#f8fafc"
    ACCENT="#ef4444"
    HILITE="#111827"
    ;;
  *)
    echo "Unknown STYLE: $STYLE" >&2
    exit 1
    ;;
esac

magick -size 1280x720 radial-gradient:"$BG_B-$BG_A" "$BG"

if [[ "$STYLE" != "white" ]]; then
  magick "$BG" \
    -fill "$ACCENT" -draw 'line 0,80 1280,250' \
    -fill "$ACCENT" -draw 'line 0,650 1280,470' \
    -blur 0x8 "$BG"
fi

magick "$FACE_FILE" -resize 520x620^ -gravity north -extent 520x620 "$FACE"

magick -size 430x210 xc:'#111827' \
  -fill "$ACCENT" -stroke '#ffffff' -strokewidth 5 -draw 'roundrectangle 18,18 412,192 30,30' \
  -stroke none -fill '#ffffff' -font "$FONT" -pointsize 48 -gravity center \
  -annotate +0-18 "$BADGE_TEXT" \
  -fill "$HILITE" -pointsize 34 -annotate +0+48 "$BOTTOM_TEXT" \
  "$BADGE"

if [[ "$STYLE" == "white" ]]; then
  magick "$BG" \
    -fill '#ffffff' -draw 'rectangle 0,0 1280,720' \
    "$BADGE" -geometry +70+80 -composite \
    "$FACE" -geometry +690+120 -composite \
    -font "$FONT" -pointsize 78 -fill '#111827' -gravity northwest -annotate +520+115 "$TOP_TEXT" \
    -stroke "$ACCENT" -strokewidth 5 -draw 'line 520,255 1040,255' \
    -stroke none "$OUT_FILE"
else
  magick "$BG" \
    "$BADGE" -geometry +440+135 -composite \
    "$FACE" -geometry +685+95 -composite \
    -font "$FONT" -pointsize 86 -stroke '#000000' -strokewidth 8 -fill '#ffffff' -gravity northwest -annotate +50+55 "$TOP_TEXT" \
    -stroke none -fill "$ACCENT" -pointsize 62 -annotate +60+625 "$BOTTOM_TEXT" \
    "$OUT_FILE"
fi

echo "Generated: $OUT_FILE"

