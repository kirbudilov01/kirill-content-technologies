#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$ROOT/png"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
SOURCE="${SOURCE:-essay.html}"

mkdir -p "$OUT"

for i in $(seq 1 10); do
  "$CHROME" \
    --headless=new \
    --disable-gpu \
    --hide-scrollbars \
    --force-device-scale-factor=1 \
    --window-size=1080,1350 \
    --screenshot="$OUT/atlasrepo-carousel-$(printf "%02d" "$i").png" \
    "file://$ROOT/$SOURCE?slide=$i" >/dev/null 2>&1
done

echo "Exported 10 slides from $SOURCE to $OUT"
