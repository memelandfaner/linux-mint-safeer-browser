#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(cat packaging/VERSION)"
BUILDER="${FLATPAK_BUILDER:-flatpak-builder}"
mkdir -p dist
"$BUILDER" --user --force-clean --repo=build/flatpak-repo build/flatpak io.github.memelandfaner.SafeerBrowser.yml
flatpak build-bundle build/flatpak-repo "dist/Safeer-Browser-${VERSION}-x86_64.flatpak" io.github.memelandfaner.SafeerBrowser master
