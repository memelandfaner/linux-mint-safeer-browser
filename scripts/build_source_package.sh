#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Debian / Launchpad PPA Source Package Generator
# Prepares .orig.tar.gz, .dsc, .debian.tar.xz, and _source.changes
# Compatible with Ubuntu 24.04 (Noble - Mint 22) and Ubuntu 22.04 (Jammy - Mint 21)
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DIR"

VERSION="1.0.7"
DISTROS=("noble" "jammy")
TARGET_DISTRO="${1:-all}"
OUT_DIR="$DIR/build/ppa"

mkdir -p "$OUT_DIR"

echo "=========================================================="
echo "📦 Generiranje Debian Source Paketa za Safeer v$VERSION"
echo "=========================================================="

# 1. Ustvari čisto izvorno drevo brez git in začasnih datotek
ORIG_DIR="$DIR/build/safeer-browser-$VERSION"
ORIG_TAR="$OUT_DIR/safeer-browser_$VERSION.orig.tar.gz"

rm -rf "$ORIG_DIR"
mkdir -p "$ORIG_DIR"

cp -r safeer_mint.py core ui assets safeer-mint.sh install.sh uninstall.sh \
      safeer-browser.desktop io.github.memelandfaner.SafeerBrowser.metainfo.xml \
      README.md LICENSE "$ORIG_DIR/"

# Odstrani pycache
find "$ORIG_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$ORIG_DIR" -name "*.pyc" -delete 2>/dev/null || true

# Ustvari .orig.tar.gz (potreben točno enkrat za Launchpad)
echo "📦 Ustvarjanje $ORIG_TAR..."
tar -czf "$ORIG_TAR" -C "$DIR/build" "safeer-browser-$VERSION"
rm -rf "$ORIG_DIR"

# 2. Funkcija za gradnjo paketa za določeno distribucijo
build_for_distro() {
    local DIST="$1"
    local REVISION="0ubuntu1~${DIST}1"
    local FULL_VER="${VERSION}-${REVISION}"
    local WORK_DIR="$DIR/build/work_${DIST}/safeer-browser-${VERSION}"

    echo ""
    echo "🔨 Gradnja izvornega paketa za: $DIST ($FULL_VER)..."
    rm -rf "$DIR/build/work_${DIST}"
    mkdir -p "$WORK_DIR"

    # Razširi izvorno kodo
    tar -xzf "$ORIG_TAR" -C "$DIR/build/work_${DIST}"
    # Kopiraj obstoječ debian/ imenik
    cp -r "$DIR/debian" "$WORK_DIR/"

    # Posodobi debian/changelog za to distribucijo
    cat << CL_EOF > "$WORK_DIR/debian/changelog"
safeer-browser (${FULL_VER}) ${DIST}; urgency=medium

  * PPA release for Ubuntu ${DIST} (Linux Mint compatible).
  * Fast native WebKitGTK browsing, zero-ad engine, and threat shield.
  * AppStream metainfo for Linux Mint Software Manager (mintinstall).
  * Onboarding setup wizard, bookmarks toolbar, and DuckDuckGo default.

 -- Safeer Sovereign Security Team <support@safeer.org>  $(date -R)
CL_EOF

    # Poveži .orig.tar.gz v nadrejeno mapo delovnega imenika (za dpkg-source)
    cp "$ORIG_TAR" "$DIR/build/work_${DIST}/safeer-browser_${VERSION}.orig.tar.gz"

    # Zgradi izvorni paket (-d omogoča gradnjo izvornega paketa brez lokalnega debhelperja, saj se gradi na Launchpadu)
    cd "$WORK_DIR"
    dpkg-buildpackage -S -sa -d -us -uc

    # Premakni rezultate v $OUT_DIR
    mv "$DIR/build/work_${DIST}"/safeer-browser_${VERSION}* "$OUT_DIR/" 2>/dev/null || true
    mv "$DIR/build/work_${DIST}"/safeer-browser_${FULL_VER}* "$OUT_DIR/" 2>/dev/null || true
    rm -rf "$DIR/build/work_${DIST}"

    echo "✅ Uspešno zgrajen izvorni paket za $DIST v $OUT_DIR"
}

# 3. Zgradi za izbrane distribucije
if [ "$TARGET_DISTRO" = "all" ]; then
    for D in "${DISTROS[@]}"; do
        build_for_distro "$D"
    done
else
    build_for_distro "$TARGET_DISTRO"
fi

cd "$DIR"

echo ""
echo "=========================================================="
echo "🎉 VSI IZVORNI PAKETI ZA PPA SO PRIPRAVLJENI V:"
echo "   $OUT_DIR"
echo "=========================================================="
ls -lh "$OUT_DIR"
echo ""
echo "Naslednji korak za nalaganje na Launchpad PPA:"
echo "1. Podpišite .changes z GPG ključem:"
echo "   debsign -k <GPG_KEY_ID> $OUT_DIR/*_source.changes"
echo "2. Naložite z dput:"
echo "   dput ppa:<tvoj-launchpad-uporabnik>/safeer $OUT_DIR/*_source.changes"
echo "=========================================================="
