#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Launchpad PPA Sign & Upload Script
# Signs source packages with GPG and uploads them via dput
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PPA_DIR="$DIR/build/ppa"
PPA_TARGET="${1:-}"
GPG_KEY="${2:-}"

echo "=========================================================="
echo "🚀 Safeer Browser — Launchpad PPA Objava"
echo "=========================================================="

if [ -z "$PPA_TARGET" ]; then
    echo "Uporaba:"
    echo "  $0 <ppa:uporabnik/ppa-ime> [GPG_KEY_ID]"
    echo ""
    echo "Primer:"
    echo "  $0 ppa:memelandfaner/safeer"
    echo "  $0 ppa:memelandfaner/safeer 1A2B3C4D"
    exit 1
fi

if [ ! -d "$PPA_DIR" ] || [ -z "$(ls -A "$PPA_DIR"/*_source.changes 2>/dev/null)" ]; then
    echo "⚠️  Izvorni paketi niso najdeni. Najprej zaženite:"
    echo "   ./scripts/build_source_package.sh all"
    exit 1
fi

# Preveri razpoložljivost orodij
if ! command -v dput >/dev/null 2>&1; then
    echo "❌ 'dput' ni nameščen. Namestite ga z:"
    echo "   sudo apt install dput devscripts"
    exit 1
fi

# Podpisovanje .changes datotek
echo ""
echo "🔑 Podpisovanje izvornih paketov z GPG..."
for CHANGES in "$PPA_DIR"/*_source.changes; do
    echo "Podpisujem: $(basename "$CHANGES")"
    if [ -n "$GPG_KEY" ]; then
        debsign -k "$GPG_KEY" "$CHANGES"
    else
        debsign "$CHANGES"
    fi
done

# Nalaganje na Launchpad PPA
echo ""
echo "📤 Nalaganje paketov v $PPA_TARGET..."
for CHANGES in "$PPA_DIR"/*_source.changes; do
    echo "Nalagam: $(basename "$CHANGES") -> $PPA_TARGET"
    dput "$PPA_TARGET" "$CHANGES"
done

echo ""
echo "=========================================================="
echo "✅ Uspešno naloženo na Launchpad PPA: $PPA_TARGET!"
echo "Ko Launchpad zaključi gradnjo paketov, bodo uporabniki na Mintu lahko namestili z:"
echo "   sudo add-apt-repository $PPA_TARGET"
echo "   sudo apt update"
echo "   sudo apt install safeer-browser"
echo "=========================================================="
