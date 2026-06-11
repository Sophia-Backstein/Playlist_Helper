#!/usr/bin/env bash
# Collect one sample of each supported media format from subfolders.
# Place this script in tests/ and run it. Dot-folders are ignored.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="$SCRIPT_DIR/collected_test_samples"
FORMATS=(mp3 m4a opus wav flac mp4 avi flv mkv webm mov)

mkdir -p "$OUT_DIR"

for fmt in "${FORMATS[@]}"; do
    file=$(find "$SCRIPT_DIR" -mindepth 2 -not -path '*/.*' -type f -iname "*.$fmt" -print -quit 2>/dev/null || true)
    if [[ -n "$file" ]]; then
        cp -n "$file" "$OUT_DIR/" 2>/dev/null && echo "  + $fmt <- $file" || true
    fi
done

cd "$OUT_DIR"
zip -r "$SCRIPT_DIR/collected_test_samples.zip" .
echo "  -> $SCRIPT_DIR/collected_test_samples.zip"
echo "DONE"
