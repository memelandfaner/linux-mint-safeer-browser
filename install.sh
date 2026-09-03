#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser - Linux Mint One-Click Installer
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/safeer-mint"
DESKTOP_DIR="$HOME/.local/share/applications"
AUTOSTART_DIR="$HOME/Namizje"

echo "=========================================================="
echo "🛡️ NAMEŠČANJE: Safeer Browser za Linux Mint"
echo "=========================================================="

# 1. Ensure permissions
chmod +x "$DIR/safeer_mint.py"
chmod +x "$DIR/safeer-mint.sh"
chmod +x "$DIR/safeer-browser.desktop"

# 2. Install to ~/.local/share/applications so it appears in Linux Mint Menu
mkdir -p "$DESKTOP_DIR"
cp "$DIR/safeer-browser.desktop" "$DESKTOP_DIR/safeer-browser.desktop"

# 3. Create shortcut on Desktop
if [[ -d "$AUTOSTART_DIR" ]]; then
    cp "$DIR/safeer-browser.desktop" "$AUTOSTART_DIR/safeer-browser.desktop"
    chmod +x "$AUTOSTART_DIR/safeer-browser.desktop"
    gio set "$AUTOSTART_DIR/safeer-browser.desktop" metadata::trusted true 2>/dev/null || true
fi

# 4. Update desktop database
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo "✅ Safeer Browser je bil uspešno nameščen!"
echo "   - Ikona je dodana na vaše Namizje"
echo "   - Aplikacija je dodana v Linux Mint meni (Internet -> Safeer Browser)"
echo "   - Zaženite z: $DIR/safeer-mint.sh"
echo "=========================================================="
