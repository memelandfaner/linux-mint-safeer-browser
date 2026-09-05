#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Linux Mint Edition Launcher
# Lightning-fast single-instance manager & instant URL handoff via Unix socket
# ==============================================================================
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
cd "$DIR"

CONFIG_DIR="$HOME/.config/safeer-mint"
mkdir -p "$CONFIG_DIR"
SOCK_FILE="$CONFIG_DIR/safeer.sock"
LOCK_FILE="$CONFIG_DIR/safeer.lock"

# Če Safeer že teče, nemudoma posreduj povezavo prek Unix socketa v nov zavihek
if [ -S "$SOCK_FILE" ]; then
    TARGET_URL="$1"
    if [ -n "$TARGET_URL" ]; then
        python3 -c "
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(1.5)
    s.connect('$SOCK_FILE')
    s.sendall(('OPEN ' + sys.argv[1]).encode('utf-8'))
    s.recv(1024)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" "$TARGET_URL" 2>/dev/null && exit 0
    else
        python3 -c "
import socket, sys
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(1.5)
    s.connect('$SOCK_FILE')
    s.sendall(b'FOCUS')
    s.recv(1024)
    s.close()
    sys.exit(0)
except Exception:
    sys.exit(1)
" 2>/dev/null && exit 0
    fi

    # Socket ni odziven (stale socket) — varno ga odstranimo z atomskim flock zaklepom
    (
        flock -x 200 2>/dev/null || true
        if ! python3 -c "
import socket
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.5)
    s.connect('$SOCK_FILE')
    s.close()
    exit(0)
except Exception:
    exit(1)
" 2>/dev/null; then
            rm -f "$SOCK_FILE"
        fi
    ) 200>"$LOCK_FILE"
fi

# 🚀 Strojno pospeševanje za Linux Mint / Ubuntu (Wayland & X11)
export WEBKIT_FORCE_COMPOSITING_MODE=1
export WEBKIT_DISABLE_COMPOSITING_MODE=0


# Zagon s sistemskim pythonom
exec /usr/bin/python3 "$DIR/safeer_mint.py" "$@"
