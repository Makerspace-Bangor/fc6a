#!/usr/bin/env python3
"""
Reassemble a byte-identical .zld file from zld_extract.py output.

A complete extraction is required. Program-only extraction deliberately omits
firmware sections and cannot recreate the original firmware-inclusive ZLD.
"""

import argparse
import hashlib
import json
from pathlib import Path


class RebuildError(ValueError):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def load_manifest(source):
    source = Path(source)
    manifest_path = source / "manifest.json" if source.is_dir() else source

    if not manifest_path.is_file():
        raise RebuildError(f"manifest not found: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        raise RebuildError(f"{manifest_path}: invalid JSON: {exc}") from exc

    return manifest_path, manifest


def read_verified(path, expected_length, expected_sha256, label):
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise RebuildError(f"{label}: cannot read {path}: {exc}") from exc

    if len(data) != expected_length:
        raise RebuildError(
            f"{label}: {path} is {len(data)} bytes, expected {expected_length}"
        )

    actual_sha256 = sha256(data)
    if actual_sha256 != expected_sha256:
        raise RebuildError(
            f"{label}: SHA-256 mismatch for {path}\n"
            f"expected: {expected_sha256}\n"
            f"actual:   {actual_sha256}"
        )

    return data


def rebuild(source, output, force=False):
    manifest_path, manifest = load_manifest(source)
    base_dir = manifest_path.parent
    output = Path(output)

    if output.exists() and not force:
        raise RebuildError(
            f"output already exists: {output}; use --force to overwrite"
        )

    sections = sorted(manifest.get("sections", []), key=lambda item: item["index"])
    if len(sections) != manifest.get("section_count"):
        raise RebuildError(
            "manifest section count does not match its section records"
        )

    missing = [
        section["type_hex"]
        for section in sections
        if not section.get("extracted") or not section.get("output_path")
    ]
    if missing:
        joined = ", ".join(missing)
        raise RebuildError(
            "incomplete extraction; missing section payloads: "
            f"{joined}. Run zld_extract.py without --program-only."
        )

    header_name = manifest.get("header_filename", "zld_header.bin")
    header_path = base_dir / header_name
    header = read_verified(
        header_path,
        manifest["header_size"],
        manifest["header_sha256"],
        "header",
    )

    rebuilt = bytearray(header)

    for section in sections:
        if len(rebuilt) != section["offset"]:
            raise RebuildError(
                f"section {section['index']} expects offset {section['offset']}, "
                f"but rebuilt file is currently {len(rebuilt)} bytes"
            )

        section_path = base_dir / section["output_path"]
        payload = read_verified(
            section_path,
            section["length"],
            section["sha256"],
            f"section {section['index']} {section['type_hex']}",
        )
        rebuilt.extend(payload)

    if len(rebuilt) != manifest["file_size"]:
        raise RebuildError(
            f"rebuilt size is {len(rebuilt)}, expected {manifest['file_size']}"
        )

    rebuilt_sha256 = sha256(rebuilt)
    expected_sha256 = manifest.get("source_sha256")
    if expected_sha256 and rebuilt_sha256 != expected_sha256:
        raise RebuildError(
            "rebuilt file does not match the original SHA-256\n"
            f"expected: {expected_sha256}\n"
            f"actual:   {rebuilt_sha256}"
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(rebuilt)

    print(f"Rebuilt: {output}")
    print(f"Size: {len(rebuilt):,} bytes")
    print(f"SHA-256: {rebuilt_sha256}")
    if expected_sha256:
        print("Result is byte-for-byte identical to the source ZLD.")


def main():
    parser = argparse.ArgumentParser(
        description="Reassemble a ZLD from a complete zld_extract.py output."
    )
    parser.add_argument(
        "source",
        type=Path,
        help="extraction directory or manifest.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        required=True,
        help="rebuilt .zld output path",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing output file",
    )
    args = parser.parse_args()

    try:
        rebuild(args.source, args.output, force=args.force)
    except (OSError, KeyError, TypeError, RebuildError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
