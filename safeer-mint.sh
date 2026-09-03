#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser - Linux Mint Edition Launcher
# Ultra-smooth single-instance manager & instant window focus
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Check if Safeer Browser is already running
EXISTING_PID=$(pgrep -f "python3.*safeer_mint.py" | grep -v "$$" | head -n 1)

if [ -n "$EXISTING_PID" ]; then
    # Focus existing window instantly
    wmctrl -x -a "safeer-browser" 2>/dev/null || xdotool search --class "safeer-browser" windowactivate 2>/dev/null || true
    exit 0
fi

# Run with system python
exec /usr/bin/python3 "$DIR/safeer_mint.py" "$@"
