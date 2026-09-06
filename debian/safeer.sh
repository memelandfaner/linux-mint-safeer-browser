#!/usr/bin/env bash
export PULSE_LATENCY_MSEC=120
export GST_PULSE_BUFFER_MS=120
exec python3 /usr/lib/safeer-browser/safeer_mint.py "$@"
