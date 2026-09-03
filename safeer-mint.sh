#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Linux Mint Edition Launcher
# Lightning-fast single-instance manager & instant URL handoff via Unix socket
# ==============================================================================
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

SOCK_FILE="$HOME/.config/safeer-mint/safeer.sock"

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
    # Če je socket neaktiven (stale socket), ga odstranimo
    rm -f "$SOCK_FILE"
fi

# Zagon s sistemskim pythonom
exec /usr/bin/python3 "$DIR/safeer_mint.py" "$@"
