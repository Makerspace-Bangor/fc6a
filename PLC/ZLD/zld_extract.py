#!/usr/bin/env python3
"""
Extract sections from IDEC DataFileManager .zld files.

Confirmed section types:
    0x1019  Firmware sent with WS77FF01
    0x1119  Firmware sent with WS77FF05

Probable section types:
    0x0010  Compiled PLC program sent with WPn
    0x0011  Supplementary data sent with W;n

The first two roles are strongly indicated by captures and section sizes, but should
still be verified against a capture made from the exact same .zld file.
"""

import argparse
import hashlib
import json
import struct
from pathlib import Path


MAGIC = b"\xff\xff\x03\x00"
BASE_HEADER_SIZE = 24
RECORD_TABLE_OFFSET = 20
RECORD_SIZE = 24
MAX_RECORD_COUNT = 64

SECTION_INFO = {
    0x0010: ("section_10_program.bin", "probable WPn compiled program"),
    0x0011: ("section_11_supplemental.bin", "probable W;n supplementary data"),
    0x1019: ("firmware_77ff01.bin", "confirmed WS77FF01 firmware"),
    0x1119: ("firmware_77ff05.bin", "confirmed WS77FF05 firmware"),
}


class ZLDError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def parse_zld(path):
    path = Path(path)
    data = path.read_bytes()

    if len(data) < BASE_HEADER_SIZE:
        raise ZLDError(f"{path}: file is too small to be a sectioned ZLD")

    if data[:4] != MAGIC:
        raise ZLDError(
            f"{path}: unexpected magic {data[:4].hex()}, expected {MAGIC.hex()}"
        )

    record_count = struct.unpack_from("<H", data, 14)[0]
    if not 1 <= record_count <= MAX_RECORD_COUNT:
        raise ZLDError(f"{path}: invalid section count {record_count}")

    header_size = BASE_HEADER_SIZE + record_count * RECORD_SIZE
    if len(data) < header_size:
        raise ZLDError(
            f"{path}: {record_count} section records require a "
            f"{header_size}-byte header, but file is only {len(data)} bytes"
        )

    declared_size = struct.unpack_from("<I", data, 16)[0]
    if declared_size + 20 != len(data):
        raise ZLDError(
            f"{path}: declared size {declared_size} does not match "
            f"actual payload size {len(data) - 20}"
        )

    sections = []
    previous_end = header_size

    for index in range(record_count):
        record_offset = RECORD_TABLE_OFFSET + index * RECORD_SIZE
        type_id, offset, length, zld_check, reserved1, reserved2 = struct.unpack_from(
            "<6I", data, record_offset
        )

        if offset < header_size:
            raise ZLDError(
                f"{path}: section {index + 1} starts at {offset}, "
                f"inside the {header_size}-byte header"
            )

        if offset + length > len(data):
            raise ZLDError(
                f"{path}: section {index + 1} range {offset}:{offset + length} "
                f"extends beyond the {len(data)}-byte file"
            )

        if offset != previous_end:
            raise ZLDError(
                f"{path}: section {index + 1} begins at {offset}, "
                f"expected contiguous offset {previous_end}"
            )

        payload = data[offset:offset + length]
        filename, role = SECTION_INFO.get(
            type_id, (f"section_{type_id:08x}.bin", "unknown section")
        )

        sections.append(
            {
                "index": index + 1,
                "type_id": type_id,
                "type_hex": f"0x{type_id:04X}",
                "offset": offset,
                "length": length,
                "zld_check": zld_check,
                "zld_check_hex": f"0x{zld_check:08X}",
                "reserved1": reserved1,
                "reserved2": reserved2,
                "filename": filename,
                "role": role,
                "sha256": sha256(payload),
                "payload": payload,
            }
        )
        previous_end = offset + length

    if previous_end != len(data):
        raise ZLDError(
            f"{path}: parsed sections end at {previous_end}, file ends at {len(data)}"
        )

    return {
        "source": str(path),
        "file_size": len(data),
        "declared_payload_size": declared_size,
        "header_size": header_size,
        "section_count": record_count,
        "header_fields": {
            "field_04": struct.unpack_from("<I", data, 4)[0],
            "field_08": struct.unpack_from("<I", data, 8)[0],
            "field_12": struct.unpack_from("<I", data, 12)[0],
        },
        "sections": sections,
    }


def print_summary(parsed):
    print(f"Source: {parsed['source']}")
    print(f"File size: {parsed['file_size']:,} bytes")
    print(f"Header size: {parsed['header_size']:,} bytes")
    print(f"Sections: {parsed['section_count']}")
    print()
    print(" #  Type      Offset      Length  Role")
    print("--  ------  ----------  ----------  ------------------------------")

    for section in parsed["sections"]:
        print(
            f"{section['index']:2d}  {section['type_hex']:>6}  "
            f"{section['offset']:10,d}  {section['length']:10,d}  "
            f"{section['role']}"
        )
        print(f"    SHA-256: {section['sha256']}")


def write_sections(parsed, output_dir, program_only=False):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        key: value for key, value in parsed.items() if key != "sections"
    }
    manifest["sections"] = []

    for section in parsed["sections"]:
        if program_only and section["type_id"] not in (0x0010, 0x0011):
            continue

        output_path = output_dir / section["filename"]
        output_path.write_bytes(section["payload"])

        metadata = {
            key: value for key, value in section.items() if key != "payload"
        }
        metadata["output_path"] = str(output_path)
        manifest["sections"].append(metadata)

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest_path


def main():
    parser = argparse.ArgumentParser(
        description="Inspect and extract IDEC DataFileManager ZLD sections."
    )
    parser.add_argument("zld", type=Path, help="input .zld file")
    parser.add_argument(
        "-o", "--output-dir", type=Path,
        help="extract sections to this directory"
    )
    parser.add_argument(
        "--program-only", action="store_true",
        help="extract only section types 0x10 and 0x11"
    )
    args = parser.parse_args()

    try:
        parsed = parse_zld(args.zld)
    except (OSError, ZLDError) as exc:
        parser.error(str(exc))

    print_summary(parsed)

    if args.output_dir:
        manifest = write_sections(
            parsed, args.output_dir, program_only=args.program_only
        )
        print()
        print(f"Extracted to: {args.output_dir}")
        print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
