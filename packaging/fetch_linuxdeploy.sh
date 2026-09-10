#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$ROOT/build/tools"
cd "$ROOT/build/tools"
curl -fL --retry 3 https://github.com/linuxdeploy/linuxdeploy/releases/download/1-alpha-20251107-1/linuxdeploy-x86_64.AppImage -o linuxdeploy.AppImage
printf '%s\n' 'c20cd71e3a4e3b80c3483cef793cda3f4e990aca14014d23c544ca3ce1270b4d  linuxdeploy.AppImage' | sha256sum -c -
chmod +x linuxdeploy.AppImage
curl -fL --retry 3 https://github.com/AppImage/type2-runtime/releases/download/continuous/runtime-x86_64 -o runtime-x86_64
printf '%s\n' '1cc49bcf1e2ccd593c379adb17c9f85a36d619088296504de95b1d06215aebbf  runtime-x86_64' | sha256sum -c -
