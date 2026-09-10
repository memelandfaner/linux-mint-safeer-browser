#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Usage: install_payload.sh DESTINATION_PREFIX [desktop-id]}"
ID="${2:-safeer-browser}"
mkdir -p "$PREFIX/bin" "$PREFIX/lib/safeer-browser" "$PREFIX/share/applications" "$PREFIX/share/metainfo" "$PREFIX/share/pixmaps"
cp -a "$ROOT/safeer_mint.py" "$ROOT/core" "$ROOT/ui" "$ROOT/assets" "$PREFIX/lib/safeer-browser/"
find "$PREFIX/lib/safeer-browser" -type d -name __pycache__ -exec rm -rf {} +
find "$PREFIX/lib/safeer-browser" -name '*.pyc' -delete
install -m755 "$ROOT/packaging/safeer-launcher" "$PREFIX/bin/safeer"
install -Dm644 "$ROOT/LICENSE" "$PREFIX/share/doc/safeer-browser/LICENSE"
ln -sf safeer "$PREFIX/bin/safeer-browser"
sed "s/^Icon=.*/Icon=$ID/" "$ROOT/packaging/safeer-browser.desktop" > "$PREFIX/share/applications/$ID.desktop"
sed "s|safeer-browser.desktop|$ID.desktop|" "$ROOT/io.github.memelandfaner.SafeerBrowser.metainfo.xml" > "$PREFIX/share/metainfo/io.github.memelandfaner.SafeerBrowser.metainfo.xml"
install -m644 "$ROOT/assets/icon.png" "$PREFIX/share/pixmaps/$ID.png"
for icon in "$ROOT/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
