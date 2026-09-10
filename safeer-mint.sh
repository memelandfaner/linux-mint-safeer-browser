#!/usr/bin/env bash
# Resolve the source checkout even when launched through a desktop symlink.
set -e
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SCRIPT_PATH")"
# Let WebKit select a supported compositor. Do not change desktop-wide settings.
export PULSE_LATENCY_MSEC="${PULSE_LATENCY_MSEC:-120}"
export GST_PULSE_BUFFER_MS="${GST_PULSE_BUFFER_MS:-120}"
# Python owns the single-instance handoff and respects XDG_CONFIG_HOME.
exec /usr/bin/python3 "$DIR/safeer_mint.py" "$@"
