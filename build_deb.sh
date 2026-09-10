#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Debian / Ubuntu / Linux Mint .deb Package Builder
# Produces production-ready safeer-browser_<version>_all.deb
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-browser"
VERSION="$(cat "$DIR/packaging/VERSION")"
ARCH="all"
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"
TAR_PACKAGE="safeer-browser-linux.tar.gz"
BUILD_ROOT="$DIR/build/deb"

echo "=========================================================="
echo "📦 Gradnja Debian paketa: $DEB_PACKAGE"
echo "=========================================================="

# Assemble the same payload as Flatpak and AppImage.
bash "$DIR/packaging/build_app_stage.sh"
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
cp -a "$DIR/build/stage/usr" "$BUILD_ROOT/"

# 6. Create DEBIAN/control
echo "📝 Generiranje DEBIAN/control..."
cat << EOF > "$BUILD_ROOT/DEBIAN/control"
Package: safeer-browser
Version: ${VERSION}
Section: web
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-soup-3.0, gir1.2-glib-2.0
Maintainer: Safeer Sovereign Security Team <support@safeer.org>
Homepage: https://github.com/memelandfaner/linux-mint-safeer-browser
Description: Sovereign, ultra-fast, and private web browser for Linux Mint & Ubuntu
 Safeer Browser is an open-source, ultra-fast web browser engineered
 specifically for Linux Mint and Ubuntu. Built natively with GTK3 and
 WebKit2GTK, it includes ad filtering, a local threat blocklist,
 bookmarks import from Firefox and Chrome, customizable portals,
 user CSS styling, and configurable JavaScript userscripts.
EOF
chmod 644 "$BUILD_ROOT/DEBIAN/control"

# 7. Create DEBIAN/postinst & DEBIAN/postrm
cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postinst"
#!/bin/sh
set -euo pipefail

if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications || true
fi

if [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi

# Register Safeer Browser into Debian alternatives system for default browser
if [ -x /usr/sbin/update-alternatives ] || [ -x /usr/bin/update-alternatives ]; then
    update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/safeer 40 || true
    update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/safeer 40 || true
fi

exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"

cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postrm"
#!/bin/sh
set -euo pipefail

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if [ -x /usr/bin/update-desktop-database ]; then
        /usr/bin/update-desktop-database -q /usr/share/applications || true
    fi
    if [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
    if [ -x /usr/sbin/update-alternatives ] || [ -x /usr/bin/update-alternatives ]; then
        update-alternatives --remove x-www-browser /usr/bin/safeer 2>/dev/null || true
        update-alternatives --remove gnome-www-browser /usr/bin/safeer 2>/dev/null || true
    fi
fi

exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postrm"

# Fix directory and control permissions strictly for dpkg-deb
find "$BUILD_ROOT" -type d -exec chmod 755 {} +
chmod 755 "$BUILD_ROOT/DEBIAN"
chmod 644 "$BUILD_ROOT/DEBIAN/control"
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"
chmod 755 "$BUILD_ROOT/DEBIAN/postrm"
chmod 755 "$BUILD_ROOT/usr/bin/safeer"

# 8. Build Debian package (all architecture)
echo "🔨 Izdelava paketa z dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DIR/$DEB_PACKAGE"

# 9. Build portable tar.gz package
echo "📦 Izdelava prenosnega arhiva: $TAR_PACKAGE..."
tar -czf "$DIR/$TAR_PACKAGE" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".git" \
    --exclude="build" \
    -C "$DIR" \
    safeer_mint.py core ui assets safeer-mint.sh install.sh uninstall.sh safeer-browser.desktop README.md LICENSE

# 10. Generate SHA256SUMS
echo "🔒 Računanje SHA256 kontrolnih vsot..."
cd "$DIR"
sha256sum "$DEB_PACKAGE" "$TAR_PACKAGE" > "$DIR/SHA256SUMS"

# 12. Verify package
echo ""
echo "=========================================================="
echo "✅ PAKETI USPEŠNO ZGRAJENI:"
echo "   All-Arch .deb: $DIR/$DEB_PACKAGE"
echo "   Portable tar : $DIR/$TAR_PACKAGE"
cat "$DIR/SHA256SUMS"
echo "=========================================================="
echo ""
echo "Preverjanje vsebine paketa:"
dpkg-deb -I "$DIR/$DEB_PACKAGE"
echo ""
echo "Paket lahko namestite z:"
echo "   sudo apt install ./$DEB_PACKAGE"
echo "ali z dvojnim klikom preko Gdebi / Upravitelja programov."
