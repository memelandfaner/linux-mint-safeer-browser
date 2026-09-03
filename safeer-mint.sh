#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser - Linux Mint Edition Launcher
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Run with system python
exec /usr/bin/python3 "$DIR/safeer_mint.py" "$@"
