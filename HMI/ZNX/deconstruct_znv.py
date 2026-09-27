#!/usr/bin/env python3
"""
deconstruct_znv.py - inspect and extract IDEC WindO/I-NV4 ZNV project files.

This is deliberately conservative. It has two jobs:

1. Parse the ZNV record layout observed in one known sample.
2. If that layout does not fit, scan the file for filename-like strings and
   report possible records without pretending their boundaries are proven.

Observed sample layout:

    0x10            "ZNV\x00"
    0x50            first record

    record + 0x00   u32 little-endian payload offset relative to record
    record + 0x04   u32 little-endian payload size
    record + 0x08   u32 unknown/checksum-like value
    record + 0x0c   u32 unknown
    record + 0x10   u32 unknown
    record + 0x14   u16 unknown
    record + 0x16   u16 padded filename-field length
    record + 0x18   filename field, NUL/padding included in field length
    record + rel    payload
    payload + size  next record

Usage:
    ./deconstruct_znv.py project.znv
    ./deconstruct_znv.py project.znv -o project_parts
    ./deconstruct_znv.py project.znv --scan-only

Output:
    <project>_znv/
        extraction.log
        manifest.json
        filename_scan.txt
        znv_header.bin
        files/
            ...
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


KNOWN_MAGIC_OFFSET = 0x10
KNOWN_FIRST_RECORD = 0x50
KNOWN_HEADER_SIZE = 24
MAX_NAME_FIELD = 4096
MAX_REL_OFFSET = 1024 * 1024

FILENAME_RE = re.compile(
    rb"(?<![A-Za-z0-9_.+\-])"
    rb"([A-Za-z0-9_+@%=\-][A-Za-z0-9_+@%=\-./\\]{0,191}"
    rb"\.[A-Za-z0-9_+@%=\-]{1,16})"
)


@dataclass
class Entry:
    index: int
    record_offset: int
    relative_data_offset: int
    data_offset: int
    size: int
    end_offset: int
    checksum_or_unknown: int
    unknown_a: int
    unknown_b: int
    unknown_c: int
    name_field_length: int
    name: str
    sha256: str
    confidence: str


def u16le(data: bytes, off: int) -> int:
    return struct.unpack_from("<H", data, off)[0]


def u32le(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_reasonable_name(name: str) -> bool:
    if not name or len(name) > 512:
        return False

    if "." not in Path(name.replace("\\", "/")).name:
        return False

    printable = sum(32 <= ord(ch) < 127 for ch in name)
    return printable == len(name)


def decode_name(raw: bytes) -> str | None:
    raw = raw.split(b"\x00", 1)[0]
    if not raw:
        return None

    try:
        name = raw.decode("ascii")
    except UnicodeDecodeError:
        return None

    if not is_reasonable_name(name):
        return None

    return name


def safe_relative_path(name: str) -> Path:
    name = name.replace("\\", "/")
    parts = []

    for part in name.split("/"):
        if not part or part in (".", ".."):
            continue

        clean = re.sub(r"[^A-Za-z0-9._+@%=-]", "_", part)
        if clean:
            parts.append(clean)

    if not parts:
        return Path("unnamed.bin")

    return Path(*parts)


def unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    for i in range(1, 10000):
        candidate = path.with_name(f"{path.stem}_{i:03d}{path.suffix}")
        if not candidate.exists():
            return candidate

    raise RuntimeError(f"could not create a unique filename for {path}")


def parse_record(data: bytes, rec: int, index: int, confidence: str) -> Entry | None:
    if rec < 0 or rec + KNOWN_HEADER_SIZE > len(data):
        return None

    rel = u32le(data, rec + 0x00)
    size = u32le(data, rec + 0x04)
    check = u32le(data, rec + 0x08)
    unk_a = u32le(data, rec + 0x0c)
    unk_b = u32le(data, rec + 0x10)
    unk_c = u16le(data, rec + 0x14)
    name_len = u16le(data, rec + 0x16)

    if rel < KNOWN_HEADER_SIZE or rel > MAX_REL_OFFSET:
        return None

    if name_len <= 0 or name_len > MAX_NAME_FIELD:
        return None

    name_start = rec + KNOWN_HEADER_SIZE
    name_end = name_start + name_len
    data_start = rec + rel
    data_end = data_start + size

    if name_end > len(data):
        return None

    if data_start < name_end:
        return None

    if data_start > len(data) or data_end > len(data):
        return None

    name = decode_name(data[name_start:name_end])
    if name is None:
        return None

    payload = data[data_start:data_end]

    return Entry(
        index=index,
        record_offset=rec,
        relative_data_offset=rel,
        data_offset=data_start,
        size=size,
        end_offset=data_end,
        checksum_or_unknown=check,
        unknown_a=unk_a,
        unknown_b=unk_b,
        unknown_c=unk_c,
        name_field_length=name_len,
        name=name,
        sha256=sha256_bytes(payload),
        confidence=confidence,
    )


def parse_known_stream(data: bytes) -> list[Entry]:
    entries = []
    pos = KNOWN_FIRST_RECORD

    while pos + KNOWN_HEADER_SIZE <= len(data):
        entry = parse_record(
            data,
            pos,
            len(entries),
            confidence="observed-layout",
        )

        if entry is None:
            break

        entries.append(entry)

        if entry.end_offset <= pos:
            break

        pos = entry.end_offset

    return entries


def filename_hits(data: bytes) -> list[tuple[int, str]]:
    hits = []
    seen = set()

    for match in FILENAME_RE.finditer(data):
        raw = match.group(1)

        try:
            name = raw.decode("ascii")
        except UnicodeDecodeError:
            continue

        key = (match.start(1), name)
        if key in seen:
            continue

        seen.add(key)
        hits.append(key)

    return hits


def scan_candidate_records(
    data: bytes,
    hits: list[tuple[int, str]],
) -> list[Entry]:
    candidates = []
    seen_records = set()

    for name_off, found_name in hits:
        rec = name_off - KNOWN_HEADER_SIZE

        if rec in seen_records:
            continue

        entry = parse_record(
            data,
            rec,
            len(candidates),
            confidence="scanned-candidate",
        )

        if entry is None:
            continue

        if not entry.name.startswith(found_name) and not found_name.startswith(entry.name):
            continue

        seen_records.add(rec)
        candidates.append(entry)

    candidates.sort(key=lambda e: e.record_offset)

    for i, entry in enumerate(candidates):
        entry.index = i

    return candidates


def hexdump(data: bytes, start: int, length: int = 64) -> str:
    chunk = data[start:start + length]
    lines = []

    for row_off in range(0, len(chunk), 16):
        row = chunk[row_off:row_off + 16]
        hex_part = " ".join(f"{b:02x}" for b in row)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(
            f"{start + row_off:08x}  {hex_part:<47}  {ascii_part}"
        )

    return "\n".join(lines)


def write_filename_scan(
    path: Path,
    data: bytes,
    hits: list[tuple[int, str]],
    candidates: list[Entry],
) -> None:
    candidate_by_name_off = {
        entry.record_offset + KNOWN_HEADER_SIZE: entry
        for entry in candidates
    }

    with path.open("w", encoding="utf-8") as f:
        f.write(f"filename-like strings found: {len(hits)}\n\n")

        for off, name in hits:
            f.write(f"0x{off:08x}  {name}\n")

            entry = candidate_by_name_off.get(off)
            if entry is not None:
                f.write(
                    "  possible record: "
                    f"record=0x{entry.record_offset:08x} "
                    f"data=0x{entry.data_offset:08x} "
                    f"size=0x{entry.size:x}\n"
                )

            context_start = max(0, off - 32)
            f.write(hexdump(data, context_start, 96))
            f.write("\n\n")


def write_log(
    path: Path,
    src: Path,
    data: bytes,
    entries: list[Entry],
    magic_ok: bool,
    mode: str,
) -> None:
    with path.open("w", encoding="utf-8") as f:
        f.write("IDEC ZNV deconstruction log\n")
        f.write("===========================\n\n")
        f.write(f"source: {src}\n")
        f.write(f"size: {len(data)} bytes / 0x{len(data):x}\n")
        f.write(
            f"magic at 0x{KNOWN_MAGIC_OFFSET:x}: "
            f"{'yes' if magic_ok else 'no'}\n"
        )
        f.write(f"parser mode: {mode}\n")
        f.write(f"entries: {len(entries)}\n\n")

        for entry in entries:
            f.write(f"[{entry.index:03d}] {entry.name}\n")
            f.write(f"  confidence:       {entry.confidence}\n")
            f.write(f"  record offset:    0x{entry.record_offset:08x}\n")
            f.write(
                f"  relative offset:  "
                f"0x{entry.relative_data_offset:08x}\n"
            )
            f.write(f"  data offset:      0x{entry.data_offset:08x}\n")
            f.write(f"  size:             {entry.size} / 0x{entry.size:x}\n")
            f.write(f"  end offset:       0x{entry.end_offset:08x}\n")
            f.write(
                f"  check/unknown:    "
                f"0x{entry.checksum_or_unknown:08x}\n"
            )
            f.write(f"  unknown A:        0x{entry.unknown_a:08x}\n")
            f.write(f"  unknown B:        0x{entry.unknown_b:08x}\n")
            f.write(f"  unknown C:        0x{entry.unknown_c:04x}\n")
            f.write(
                f"  name field len:   "
                f"{entry.name_field_length} / "
                f"0x{entry.name_field_length:x}\n"
            )
            f.write(f"  sha256:           {entry.sha256}\n\n")


def write_manifest(
    path: Path,
    src: Path,
    data: bytes,
    entries: list[Entry],
    magic_ok: bool,
    mode: str,
) -> None:
    manifest = {
        "source": str(src),
        "source_size": len(data),
        "sha256": sha256_bytes(data),
        "znv_magic_offset": KNOWN_MAGIC_OFFSET,
        "znv_magic_present": magic_ok,
        "first_record_offset_assumed": KNOWN_FIRST_RECORD,
        "parser_mode": mode,
        "entry_count": len(entries),
        "entries": [asdict(entry) for entry in entries],
    }

    path.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def extract_entries(data: bytes, entries: list[Entry], out_dir: Path) -> None:
    files_dir = out_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)

    for entry in entries:
        relative = safe_relative_path(entry.name)
        out_file = unique_path(files_dir / relative)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        payload = data[entry.data_offset:entry.end_offset]
        out_file.write_bytes(payload)

        print(
            f"[{entry.index:03d}] "
            f"0x{entry.data_offset:08x} "
            f"{entry.size:10d}  "
            f"{entry.name}"
        )


def default_output_dir(src: Path) -> Path:
    return src.with_name(f"{src.stem}_znv")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Deconstruct and inspect IDEC ZNV project containers"
    )
    parser.add_argument("znv", type=Path, help="input .znv file")
    parser.add_argument(
        "-o",
        "--outdir",
        type=Path,
        help="output directory; default is <input-stem>_znv",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="do not extract payloads; only write logs and scans",
    )
    args = parser.parse_args(argv)

    src = args.znv

    if not src.is_file():
        raise SystemExit(f"file not found: {src}")

    data = src.read_bytes()
    out_dir = args.outdir or default_output_dir(src)
    out_dir.mkdir(parents=True, exist_ok=True)

    magic_ok = (
        len(data) >= KNOWN_MAGIC_OFFSET + 4
        and data[KNOWN_MAGIC_OFFSET:KNOWN_MAGIC_OFFSET + 4] == b"ZNV\x00"
    )

    entries = parse_known_stream(data)

    if entries:
        mode = "observed-layout"
    else:
        hits = filename_hits(data)
        entries = scan_candidate_records(data, hits)
        mode = "candidate-scan"
    hits = filename_hits(data)

    header_len = min(KNOWN_FIRST_RECORD, len(data))
    (out_dir / "znv_header.bin").write_bytes(data[:header_len])

    write_filename_scan(
        out_dir / "filename_scan.txt",
        data,
        hits,
        entries,
    )
    write_log(
        out_dir / "extraction.log",
        src,
        data,
        entries,
        magic_ok,
        mode,
    )
    write_manifest(
        out_dir / "manifest.json",
        src,
        data,
        entries,
        magic_ok,
        mode,
    )

    print(f"source: {src}")
    print(f"size:   {len(data)} bytes / 0x{len(data):x}")
    print(f"magic:  {'ZNV at 0x10' if magic_ok else 'not confirmed'}")
    print(f"mode:   {mode}")
    print(f"found:  {len(entries)} record(s)")
    print()

    if not args.scan_only and entries:
        extract_entries(data, entries, out_dir)

    print()
    print(f"log:      {out_dir / 'extraction.log'}")
    print(f"manifest: {out_dir / 'manifest.json'}")
    print(f"scan:     {out_dir / 'filename_scan.txt'}")

    if not entries:
        print()
        print("No extractable records were confirmed.")
        print("Check filename_scan.txt for candidate filenames and nearby bytes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
