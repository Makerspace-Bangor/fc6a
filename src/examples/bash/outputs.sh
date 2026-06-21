#!/bin/bash
set -euo pipefail

HOST="192.168.1.50"
TCP_PORT=2101  
DELAY=0.15

send_frame() {
    local frame="$1"

    printf '[TX] '
    printf '%b' "$frame" | xxd -p -c 256 | sed 's/../& /g'

    # send raw bytes over TCP
    printf '%b' "$frame" >&3
    sleep "$DELAY"
}

echo "[*] Connecting to ${HOST}:${TCP_PORT} ..."

# Open a bidirectional TCP socket on fd 3
exec 3<>"/dev/tcp/${HOST}/${TCP_PORT}"

echo "[*] ON sequence"
send_frame '\x05FF0Wy000012A\r'
send_frame '\x05FF0Wy000112B\r'
send_frame '\x05FF0Wy0002128\r'
send_frame '\x05FF0Wy0003129\r'
send_frame '\x05FF0Wy000412E\r'
send_frame '\x05FF0Wy000512F\r'
send_frame '\x05FF0Wy000612C\r'
send_frame '\x05FF0Wy000712D\r'

sleep 5

echo "[*] OFF sequence"
send_frame '\x05FF0Wy000702C\r'
send_frame '\x05FF0Wy000602D\r'
send_frame '\x05FF0Wy000502E\r'
send_frame '\x05FF0Wy000402F\r'
send_frame '\x05FF0Wy0003028\r'
send_frame '\x05FF0Wy0002029\r'
send_frame '\x05FF0Wy000102A\r'
send_frame '\x05FF0Wy000002B\r'

exec 3>&-
echo "[*] Done"
