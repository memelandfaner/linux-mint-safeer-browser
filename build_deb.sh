#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Debian / Ubuntu / Linux Mint .deb Package Builder
# Produces production-ready safeer-browser_1.0.4_amd64.deb
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-browser"
VERSION="1.0.4"
ARCH="amd64"
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"
BUILD_ROOT="$DIR/build/deb"

echo "=========================================================="
echo "📦 Gradnja Debian paketa: $DEB_PACKAGE"
echo "=========================================================="

# 1. Clean previous build tree
rm -rf "$DIR/build"
mkdir -p "$BUILD_ROOT/DEBIAN"
mkdir -p "$BUILD_ROOT/usr/bin"
mkdir -p "$BUILD_ROOT/usr/lib/safeer-browser"
mkdir -p "$BUILD_ROOT/usr/share/applications"
mkdir -p "$BUILD_ROOT/usr/share/pixmaps"

# 2. Copy application code and assets
echo "📁 Kopiranje datotek aplikacije..."
cp "$DIR/safeer_mint.py" "$BUILD_ROOT/usr/lib/safeer-browser/"
cp -r "$DIR/core" "$BUILD_ROOT/usr/lib/safeer-browser/"
cp -r "$DIR/ui" "$BUILD_ROOT/usr/lib/safeer-browser/"
cp -r "$DIR/assets" "$BUILD_ROOT/usr/lib/safeer-browser/"

# Clean any pycache in build tree
find "$BUILD_ROOT/usr/lib/safeer-browser" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_ROOT/usr/lib/safeer-browser" -name "*.pyc" -delete 2>/dev/null || true

# 3. Create launcher scripts in /usr/bin
cat << 'EOF' > "$BUILD_ROOT/usr/bin/safeer"
#!/usr/bin/env bash
export PULSE_LATENCY_MSEC=120
export GST_PULSE_BUFFER_MS=120
exec python3 /usr/lib/safeer-browser/safeer_mint.py "$@"
EOF
chmod 755 "$BUILD_ROOT/usr/bin/safeer"
ln -sf "safeer" "$BUILD_ROOT/usr/bin/safeer-browser"

# 4. Create Desktop entry
cat << 'EOF' > "$BUILD_ROOT/usr/share/applications/safeer-browser.desktop"
[Desktop Entry]
Version=1.0
Type=Application
Name=Safeer Browser
GenericName=Web Browser
GenericName[sl]=Spletni brskalnik
GenericName[de]=Webbrowser
GenericName[es]=Navegador Web
GenericName[fr]=Navigateur Web
GenericName[it]=Browser Web
Comment=Sovereign, fast and private web browser for Linux Mint & Ubuntu
Comment[sl]=Suveren, ultra-hiter in zaseben spletni brskalnik za Linux Mint in Ubuntu
Exec=/usr/bin/safeer-browser %U
Icon=safeer-browser
Terminal=false
StartupNotify=true
StartupWMClass=safeer-browser
Categories=Network;WebBrowser;
MimeType=text/html;text/xml;application/xhtml+xml;x-scheme-handler/http;x-scheme-handler/https;
Actions=new-window;new-private-window;

[Desktop Action new-window]
Name=New Window
Name[sl]=Novo okno
Exec=/usr/bin/safeer-browser

[Desktop Action new-private-window]
Name=New Private Window
Name[sl]=Novo zasebno okno
Exec=/usr/bin/safeer-browser --incognito
EOF
chmod 644 "$BUILD_ROOT/usr/share/applications/safeer-browser.desktop"

# 5. Generate and install crisp hicolor icons
echo "🎨 Ustvarjanje hicolor ikon..."
cp "$DIR/assets/icon.png" "$BUILD_ROOT/usr/share/pixmaps/safeer-browser.png"
chmod 644 "$BUILD_ROOT/usr/share/pixmaps/safeer-browser.png"

python3 - << PYEOF
import os
from PIL import Image

src = "$DIR/assets/icon.png"
base = "$BUILD_ROOT/usr/share/icons/hicolor"
sizes = [16, 24, 32, 48, 64, 128, 256, 512]

if os.path.exists(src):
    try:
        img = Image.open(src)
        for s in sizes:
            target_dir = os.path.join(base, f"{s}x{s}", "apps")
            os.makedirs(target_dir, exist_ok=True)
            out_path = os.path.join(target_dir, "safeer-browser.png")
            resized = img.resize((s, s), Image.Resampling.LANCZOS)
            resized.save(out_path, "PNG", optimize=True)
            os.chmod(out_path, 0o644)
    except Exception as e:
        print(f"Napaka pri generiranju ikon: {e}")
PYEOF

# 6. Create DEBIAN/control
echo "📝 Generiranje DEBIAN/control..."
cat << EOF > "$BUILD_ROOT/DEBIAN/control"
Package: safeer-browser
Version: ${VERSION}
Section: web
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-glib-2.0
Maintainer: Safeer Sovereign Security Team <support@safeer.org>
Homepage: https://github.com/memelandfaner/linux-mint-safeer-browser
Description: Sovereign, ultra-fast, and private web browser for Linux Mint & Ubuntu
 Safeer Browser is an open-source, ultra-fast web browser engineered
 specifically for Linux Mint and Ubuntu. Built natively with GTK3 and
 WebKit2GTK, it provides instant loading, 0-ad blocking, threat shield
 protection, 1-click bookmarks import from Firefox and Chrome, customizable
 portals, user CSS styling, and Tampermonkey-compatible UserScripts.
EOF
chmod 644 "$BUILD_ROOT/DEBIAN/control"

# 7. Create DEBIAN/postinst & DEBIAN/postrm
cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postinst"
#!/bin/sh
set -e

if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications || true
fi

if [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi

exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"

cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postrm"
#!/bin/sh
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if [ -x /usr/bin/update-desktop-database ]; then
        /usr/bin/update-desktop-database -q /usr/share/applications || true
    fi
    if [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
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

# 8. Build Debian package
echo "🔨 Izdelava paketa z dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DIR/$DEB_PACKAGE"

# 9. Verify package
echo ""
echo "=========================================================="
echo "✅ PAKET USPEŠNO ZGRAJEN:"
echo "   Datoteka: $DIR/$DEB_PACKAGE"
SIZE=$(du -h "$DIR/$DEB_PACKAGE" | cut -f1)
SHA=$(sha256sum "$DIR/$DEB_PACKAGE" | cut -d' ' -f1)
echo "   Velikost: $SIZE"
echo "   SHA-256 : $SHA"
echo "=========================================================="
echo ""
echo "Preverjanje vsebine paketa:"
dpkg-deb -I "$DIR/$DEB_PACKAGE"
echo ""
echo "Paket lahko namestite z:"
echo "   sudo apt install ./$DEB_PACKAGE"
echo "ali z dvojnim klikom preko Gdebi / Upravitelja programov."
