#!/bin/bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 file.ZNX" >&2
    exit 2
fi

SRC="$(readlink -f "$1")"
HERE="$(cd "$(dirname "$0")" && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

OUTDIR="$TMP/extracted"
REBUILT="$TMP/rebuilt.ZNX"

python3 "$HERE/extract_znx_fixed.py" "$SRC" -o "$OUTDIR"
python3 "$HERE/repack_znx_fixed.py" "$OUTDIR" "$REBUILT"

echo
echo "Original:"
sha256sum "$SRC"
echo "Rebuilt:"
sha256sum "$REBUILT"
echo

if cmp -s "$SRC" "$REBUILT"; then
    echo "PASS: rebuilt ZNX is byte-for-byte identical"
    exit 0
fi

echo "FAIL: rebuilt ZNX differs from original" >&2
cmp -l "$SRC" "$REBUILT" | head -20 || true
exit 1
