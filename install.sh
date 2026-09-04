#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Linux Mint & Ubuntu One-Click Installer
# Full XDG integration: App menu, Desktop shortcut, Icons, and 'safeer' CLI
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

echo "=========================================================="
echo "🛡️ NAMEŠČANJE: Safeer Browser za Linux Mint"
echo "=========================================================="

# Preveri potrebne sistemske pakete (Python, GTK3, WebKit2GTK)
MISSING_PKGS=()
for pkg in python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -ne 0 ]; then
    echo "⚠️  OPOZORILO: Manjkajo naslednji sistemski paketi:"
    echo "   ${MISSING_PKGS[*]}"
    echo "   Za polno delovanje jih namestite z ukazom:"
    echo "   sudo apt update && sudo apt install -y ${MISSING_PKGS[*]}"
    echo "----------------------------------------------------------"
fi

# 1. Ensure execute permissions
chmod +x "$DIR/safeer_mint.py"
chmod +x "$DIR/safeer-mint.sh"
chmod +x "$DIR/safeer-browser.desktop"

# 2. Install executable into ~/.local/bin so user can run 'safeer' from anywhere
mkdir -p "$BIN_DIR"
ln -sf "$DIR/safeer-mint.sh" "$BIN_DIR/safeer"
ln -sf "$DIR/safeer-mint.sh" "$BIN_DIR/safeer-browser"

# Ensure ~/.local/bin is in PATH for current session if not already
export PATH="$BIN_DIR:$PATH"

# 3. Install App Icon to standard hicolor directory
if [[ -f "$DIR/assets/icon.png" ]]; then
    for size in 256x256 128x128 64x64 48x48 32x32; do
        mkdir -p "$ICON_BASE/$size/apps"
        cp "$DIR/assets/icon.png" "$ICON_BASE/$size/apps/safeer-browser.png"
    done
    mkdir -p "$HOME/.local/share/pixmaps"
    cp "$DIR/assets/icon.png" "$HOME/.local/share/pixmaps/safeer-browser.png"
fi

# 4. Install .desktop file to application menu
mkdir -p "$DESKTOP_DIR"
sed -e "s|Exec=safeer-browser|Exec=$BIN_DIR/safeer-browser|g" \
    "$DIR/safeer-browser.desktop" > "$DESKTOP_DIR/safeer-browser.desktop"
chmod +x "$DESKTOP_DIR/safeer-browser.desktop"

# 5. Create Desktop shortcut if Desktop or Namizje exists
for d in "$HOME/Namizje" "$HOME/Desktop"; do
    if [[ -d "$d" ]]; then
        cp "$DESKTOP_DIR/safeer-browser.desktop" "$d/safeer-browser.desktop"
        chmod +x "$d/safeer-browser.desktop"
        gio set "$d/safeer-browser.desktop" metadata::trusted true 2>/dev/null || true
    fi
done

# 6. Update desktop and icon caches
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true

echo "✅ Safeer Browser je bil uspešno nameščen!"
echo "   - Ukaz v terminalu: 'safeer' ali 'safeer-browser [URL]'"
echo "   - Bližnjica na namizju: Safeer Browser"
echo "   - Linux Mint Meni: Internet -> Safeer Browser"
echo "   - Zagon z enim klikom: $DIR/safeer-mint.sh"
echo "=========================================================="
