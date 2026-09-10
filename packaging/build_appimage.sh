#!/usr/bin/env bash
# Release builds run on Ubuntu 22.04 (glibc 2.35); newer hosts are diagnostic only.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ "$(uname -m)" = x86_64 ] || { echo 'AppImage currently supports x86_64 only' >&2; exit 1; }
if [ "$(getconf GNU_LIBC_VERSION | cut -d' ' -f2)" != 2.35 ] && [ "${ALLOW_NEWER_GLIBC:-0}" != 1 ]; then
    echo 'Build release AppImages on Ubuntu 22.04. Set ALLOW_NEWER_GLIBC=1 for a host-specific diagnostic build.' >&2
    exit 1
fi
: "${LINUXDEPLOY:?Set LINUXDEPLOY to the verified linuxdeploy executable}"
export APPIMAGE_EXTRACT_AND_RUN=1
bash packaging/build_app_stage.sh
APPDIR="$ROOT/build/Safeer.AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR" "$ROOT/dist"
cp -a build/stage/usr "$APPDIR/"
python3 packaging/prepare_appdir.py "$APPDIR"
install -m755 packaging/AppRun "$APPDIR/AppRun"
# Resolve ELF dependencies and emit the AppImage in one pass.
export LDAI_RUNTIME_FILE="${LDAI_RUNTIME_FILE:-$ROOT/build/tools/runtime-x86_64}"
[ -f "$LDAI_RUNTIME_FILE" ] || { echo "Run packaging/fetch_linuxdeploy.sh first" >&2; exit 1; }
export VERSION="$(cat packaging/VERSION)"
export OUTPUT="$ROOT/dist/Safeer-Browser-${VERSION}-x86_64.AppImage"
"$LINUXDEPLOY" --appdir "$APPDIR" --executable "$APPDIR/usr/bin/python3" \
    --desktop-file "$APPDIR/usr/share/applications/io.github.memelandfaner.SafeerBrowser.desktop" \
    --icon-file "$APPDIR/usr/share/icons/hicolor/256x256/apps/safeer-browser.png" \
    --custom-apprun "$ROOT/packaging/AppRun" --output appimage
