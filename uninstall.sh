#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Linux Mint & Ubuntu Clean Uninstaller
# Removes CLI binaries, desktop shortcuts, application menu entries, and icons
# ==============================================================================
set -e

BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
CONFIG_DIR="$HOME/.config/safeer-mint"
CACHE_DIR="$HOME/.cache/safeer_mint.py"

echo "=========================================================="
echo "🗑️ ODSTRANJEVANJE: Safeer Browser iz Linux sistema"
echo "=========================================================="

# 1. Zaustavi morebitne tekoče procese
echo "1. Ustavljanje morebitnih aktivnih procesov Safeer..."
pkill -f safeer_mint.py 2>/dev/null || true
pkill -f safeer-mint.sh 2>/dev/null || true

# 2. Odstrani zaganjalne povezave (CLI)
echo "2. Odstranjevanje povezav v $BIN_DIR..."
rm -f "$BIN_DIR/safeer" "$BIN_DIR/safeer-browser"

# 3. Odstrani .desktop datoteko iz menija aplikacij
echo "3. Odstranjevanje menijske bližnjice..."
rm -f "$DESKTOP_DIR/safeer-browser.desktop"

# 4. Odstrani bližnjice z namizja
echo "4. Odstranjevanje bližnjic z namizja..."
for d in "$HOME/Namizje" "$HOME/Desktop"; do
    if [[ -d "$d" ]]; then
        rm -f "$d/safeer-browser.desktop" "$d/Safeer-Browser.desktop" 2>/dev/null || true
    fi
done

# 5. Odstrani ikone
echo "5. Odstranjevanje namenske ikone..."
rm -f "$HOME/.local/share/pixmaps/safeer-browser.png"
for size in 512x512 256x256 128x128 64x64 48x48 32x32 24x24 16x16; do
    rm -f "$ICON_BASE/$size/apps/safeer-browser.png" 2>/dev/null || true
done

# 6. Počisti začasne predpomnilnike in zastarele sockete
echo "6. Čiščenje predpomnilnika in začasnih socketov..."
rm -rf "$CACHE_DIR"
rm -f "$CONFIG_DIR/safeer.sock" "$CONFIG_DIR/safeer.lock" 2>/dev/null || true

# Če je podana zastavica --purge, odstrani tudi uporabniške nastavitve in zaznamke
if [[ "$1" == "--purge" ]]; then
    echo "⚠️ --purge: Odstranjevanje uporabniškega profila ($CONFIG_DIR)..."
    rm -rf "$CONFIG_DIR"
fi

# 7. Posodobi sistemske baze namizja in ikon
echo "7. Posodabljanje predpomnilnika ikon in namiznih povezav..."
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true

echo "✅ Safeer Browser je bil uspešno odstranjen iz sistema!"
echo "=========================================================="
