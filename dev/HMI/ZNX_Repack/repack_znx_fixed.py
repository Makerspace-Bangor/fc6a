#!/usr/bin/env python3
"""
Repack an IDEC HMI ZNX container from files extracted by extract_znx_fixed.py.

Default mode is deliberately strict: payload sizes must be unchanged and the
result must match the original container SHA-256 recorded in .znx-meta.json.

Usage:
    ./repack_znx_fixed.py extracted/ rebuilt.ZNX
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

META_NAME = ".znx-meta.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unb64(text: str) -> bytes:
    return base64.b64decode(text.encode("ascii"))


def load_meta(indir: Path) -> dict:
    path = indir / META_NAME
    if not path.exists():
        raise FileNotFoundError(
            f"missing {path}; exact repacking requires metadata from extraction"
        )

    meta = json.loads(path.read_text(encoding="utf-8"))
    if meta.get("format") != "idec-znx-exact-roundtrip-v1":
        raise ValueError(f"unsupported metadata format: {meta.get('format')!r}")
    return meta


def repack_exact(indir: Path, output: Path) -> str:
    meta = load_meta(indir)
    out = bytearray(unb64(meta["prefix_b64"]))

    for entry in meta["entries"]:
        path = indir / entry["name"]
        if not path.exists():
            raise FileNotFoundError(f"missing payload file: {path}")

        payload = path.read_bytes()
        expected_size = int(entry["size"])
        if len(payload) != expected_size:
            raise ValueError(
                f"{entry['name']}: size changed from {expected_size} to {len(payload)}; "
                "exact roundtrip mode only accepts unchanged payload sizes"
            )

        expected_sha = entry["payload_sha256"]
        actual_sha = sha256_bytes(payload)
        if actual_sha != expected_sha:
            raise ValueError(
                f"{entry['name']}: payload SHA-256 changed\n"
                f"  expected: {expected_sha}\n"
                f"  actual:   {actual_sha}"
            )

        out += payload
        out += unb64(entry.get("gap_after_b64", ""))

    expected_size = int(meta["source_size"])
    if len(out) != expected_size:
        raise ValueError(
            f"rebuilt size mismatch: got {len(out)}, expected {expected_size}"
        )

    actual_sha = sha256_bytes(out)
    expected_sha = meta["source_sha256"]
    output.write_bytes(out)

    if actual_sha != expected_sha:
        raise ValueError(
            f"container SHA-256 mismatch after rebuild\n"
            f"  expected: {expected_sha}\n"
            f"  actual:   {actual_sha}"
        )

    return actual_sha


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Exactly rebuild an extracted IDEC HMI ZNX container"
    )
    ap.add_argument("directory", type=Path, help="directory produced by extractor")
    ap.add_argument("output", type=Path, help="output .ZNX file")
    args = ap.parse_args(argv)

    try:
        digest = repack_exact(args.directory, args.output)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {args.output}")
    print(f"sha256: {digest}")
    print("EXACT ROUNDTRIP MATCH")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
