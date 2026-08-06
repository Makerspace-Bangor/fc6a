#!/bin/bash
# if you have code on the PLC, which contradicts this code, exact results may vary.
# Else, this code will turn on all outputs, then turn off all outputs/
PORT="/dev/ttyACM0"
BAUD=9600

echo "[*] Configue $PORT ..."
stty -F "$PORT" "$BAUD" cs8 -cstopb parenb -parodd raw -echo -hupcl

# keep it open
exec 3>"$PORT"

send_frame() {
    local frame="$1"
    printf '[TX] '
    printf '%b' "$frame" | xxd -p -c 256 | sed 's/../& /g'
    printf '%b' "$frame" >&3
    sleep 0.15
}

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

# Close once at the end
exec 3>&-
