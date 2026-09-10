#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAGE="$ROOT/build/stage"
rm -rf "$STAGE"
bash "$ROOT/packaging/install_payload.sh" "$STAGE/usr"
echo "Stage ready: $STAGE"
