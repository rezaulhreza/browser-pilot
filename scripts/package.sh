#!/bin/sh
# Build the zip that is uploaded to the Chrome Web Store: the extension folder and nothing else.
set -eu

HERE="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(sed -n 's/.*"version": *"\([^"]*\)".*/\1/p' "$HERE/extension/manifest.json")"
OUT="$HERE/dist/browser-pilot-$VERSION.zip"

mkdir -p "$HERE/dist"
rm -f "$OUT"
(cd "$HERE/extension" && zip -q -r -X "$OUT" . -x '.*' -x '*/.*')
echo "Wrote $OUT"
