#!/usr/bin/env python3
"""
znx_info.py - inspect IDEC ZNX HMI update packages.

Goal: provide evidence for what changed between ZNX files without unpacking the
whole Linux filesystem by default.

Examples:
  ./znx_info.py Read_regs.ZNX
  ./znx_info.py *.ZNX --csv znx_report.csv --json znx_report.json
  ./znx_info.py *.ZNX --no-nested
"""
from __future__ import annotations

import argparse
import binascii
import csv
import hashlib
import io
import json
import os
import struct
import sys
import tarfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Iterable

ZNX_MAGIC = b"ZNX\x00"
PAYLOAD_BIAS = 0x1C
ENTRY_TABLE_OFFSET = 0x1C


@dataclass
class ZnxEntry:
    index: int
    table_offset: int
    stored_offset: int
    payload_offset: int
    size: int
    mystery: int
    name_len: int
    name: str
    sha256: str = ""
    crc32: str = ""


@dataclass
class ZnxInfo:
    path: str
    file: str
    size: int
    magic: str
    header_hex: str
    header_total_minus_0x1c: int | None
    entries: list[ZnxEntry]
    os_release: dict[str, str]
    etc_version: str
    etc_timestamp: str
    nested_archives: list[str]
    warnings: list[str]


def u32le(data: bytes, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def safe_name(name: str) -> str:
    # For display/inventory only; not used for extraction here.
    name = name.replace("\\", "/").split("/")[-1]
    return "".join(c if c.isalnum() or c in "._-+" else "_" for c in name) or "unnamed"


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def crc32_hex(data: bytes) -> str:
    return f"{binascii.crc32(data) & 0xffffffff:08x}"


def parse_znx(path: Path, hash_members: bool = True) -> tuple[bytes, list[ZnxEntry], list[str]]:
    data = path.read_bytes()
    warnings: list[str] = []
    if len(data) < ENTRY_TABLE_OFFSET:
        raise ValueError("file too small to be a ZNX")
    if data[:4] != ZNX_MAGIC:
        raise ValueError(f"bad magic {data[:4]!r}; expected {ZNX_MAGIC!r}")

    entries: list[ZnxEntry] = []
    off = ENTRY_TABLE_OFFSET
    prev_table_off = off

    # The ZNX files seen so far put a compact entry table before payloads.
    # Stop when the next entry header would overlap the first payload.
    while off + 20 <= len(data):
        if entries:
            first_payload = min(e.payload_offset for e in entries)
            if off >= first_payload:
                break

        idx = u32le(data, off)
        stored = u32le(data, off + 4)
        size = u32le(data, off + 8)
        mystery = u32le(data, off + 12)
        name_len = u32le(data, off + 16)

        # Sanity checks: prevent treating payload bytes as directory entries.
        if idx == 0 or idx > 10000:
            if not entries:
                warnings.append(f"entry table did not start cleanly at 0x{off:x}")
            break
        if name_len == 0 or name_len > 4096:
            warnings.append(f"stopping at 0x{off:x}: unreasonable name_len {name_len}")
            break
        name_start = off + 20
        name_end = name_start + name_len
        if name_end > len(data):
            warnings.append(f"stopping at 0x{off:x}: name exceeds file size")
            break

        raw_name = data[name_start:name_end]
        name = raw_name.split(b"\x00", 1)[0].decode("utf-8", "replace")
        if not name:
            warnings.append(f"stopping at 0x{off:x}: empty entry name")
            break

        payload_offset = stored + PAYLOAD_BIAS
        payload_end = payload_offset + size
        if payload_offset < name_end or payload_end > len(data):
            warnings.append(
                f"entry {idx} {name!r} points outside file: "
                f"offset=0x{payload_offset:x} size=0x{size:x}"
            )
            break

        entry = ZnxEntry(
            index=idx,
            table_offset=off,
            stored_offset=stored,
            payload_offset=payload_offset,
            size=size,
            mystery=mystery,
            name_len=name_len,
            name=name,
        )
        if hash_members:
            blob = data[payload_offset:payload_end]
            entry.sha256 = sha256_hex(blob)
            entry.crc32 = crc32_hex(blob)
        entries.append(entry)

        prev_table_off = off
        off = name_end

    if not entries:
        warnings.append("no ZNX entries found")

    # Check for gaps/overlaps in payload region.
    ordered = sorted(entries, key=lambda e: e.payload_offset)
    for a, b in zip(ordered, ordered[1:]):
        a_end = a.payload_offset + a.size
        if a_end > b.payload_offset:
            warnings.append(f"payload overlap: {a.name} overlaps {b.name}")
        elif a_end < b.payload_offset:
            warnings.append(f"payload gap: 0x{a_end:x}..0x{b.payload_offset:x}")

    return data, entries, warnings


def tar_read_text(tf: tarfile.TarFile, candidates: Iterable[str]) -> str:
    names = set(tf.getnames())
    for cand in candidates:
        variants = [cand, "./" + cand.lstrip("./"), cand.lstrip("./")]
        for v in variants:
            if v in names:
                f = tf.extractfile(v)
                if f:
                    return f.read().decode("utf-8", "replace").strip()
    return ""


def parse_os_release(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"')
        out[k] = v
    return out


def inspect_tar_xz(blob: bytes, max_depth: int = 2) -> tuple[dict[str, str], str, str, list[str], list[str]]:
    """Return os-release dict, /etc/version, /etc/timestamp, nested .tar.xz paths, warnings."""
    warnings: list[str] = []
    os_release: dict[str, str] = {}
    etc_version = ""
    etc_timestamp = ""
    nested: list[str] = []

    def walk_tar(blob2: bytes, prefix: str, depth: int) -> None:
        nonlocal os_release, etc_version, etc_timestamp, nested
        try:
            with tarfile.open(fileobj=io.BytesIO(blob2), mode="r:*") as tf:
                members = tf.getmembers()
                names = [m.name for m in members]

                if not os_release:
                    txt = tar_read_text(tf, ["etc/os-release", "usr/lib/os-release"])
                    if txt:
                        os_release = parse_os_release(txt)
                if not etc_version:
                    etc_version = tar_read_text(tf, ["etc/version"])
                if not etc_timestamp:
                    etc_timestamp = tar_read_text(tf, ["etc/timestamp"])

                for m in members:
                    n = m.name
                    if n.lower().endswith((".tar.xz", ".txz")):
                        full = f"{prefix}{n}" if prefix else n
                        nested.append(full)
                        if depth < max_depth and m.isfile():
                            f = tf.extractfile(m)
                            if f:
                                try:
                                    walk_tar(f.read(), full + " -> ", depth + 1)
                                except Exception as e:
                                    warnings.append(f"could not inspect nested archive {full}: {e}")
        except Exception as e:
            warnings.append(f"could not inspect tar archive at {prefix or '<top>'}: {e}")

    walk_tar(blob, "", 0)
    return os_release, etc_version, etc_timestamp, sorted(set(nested)), warnings


def build_info(path: Path, nested: bool = True, hash_members: bool = True) -> ZnxInfo:
    data, entries, warnings = parse_znx(path, hash_members=hash_members)
    header_hex = data[:ENTRY_TABLE_OFFSET].hex()
    header_total = u32le(data, 0x18) if len(data) >= 0x1C else None
    os_release: dict[str, str] = {}
    etc_version = ""
    etc_timestamp = ""
    nested_archives: list[str] = []

    if nested:
        for e in entries:
            if e.name.lower().endswith((".tar.xz", ".txz")):
                blob = data[e.payload_offset:e.payload_offset + e.size]
                osr, ver, ts, nests, warns = inspect_tar_xz(blob)
                if osr and not os_release:
                    os_release = osr
                if ver and not etc_version:
                    etc_version = ver
                if ts and not etc_timestamp:
                    etc_timestamp = ts
                nested_archives.extend([f"{e.name} -> {n}" for n in nests])
                warnings.extend(warns)

    return ZnxInfo(
        path=str(path),
        file=path.name,
        size=len(data),
        magic=data[:4].decode("latin1", "replace"),
        header_hex=header_hex,
        header_total_minus_0x1c=header_total,
        entries=entries,
        os_release=os_release,
        etc_version=etc_version,
        etc_timestamp=etc_timestamp,
        nested_archives=sorted(set(nested_archives)),
        warnings=warnings,
    )


def print_info(info: ZnxInfo, verbose: bool = False) -> None:
    print(f"\n{info.file}")
    print("=" * len(info.file))
    print(f"size: 0x{info.size:x} ({info.size} bytes)")
    if info.header_total_minus_0x1c is not None:
        expected = info.size - PAYLOAD_BIAS
        ok = "OK" if info.header_total_minus_0x1c == expected else f"expected 0x{expected:x}"
        print(f"header total-0x1c: 0x{info.header_total_minus_0x1c:x} ({ok})")

    print(f"members: {len(info.entries)}")
    print("      offset          size        stored      mystery   crc32     sha256                                                            name")
    print("------------  ------------  ------------  ------------  --------  ----------------------------------------------------------------  ----------------")
    for e in info.entries:
        print(
            f"0x{e.payload_offset:08x}  0x{e.size:08x}  0x{e.stored_offset:08x}  "
            f"0x{e.mystery:08x}  {e.crc32 or '-':8}  {(e.sha256 or '-')[:64]:64}  {e.name}"
        )

    if info.os_release or info.etc_version or info.etc_timestamp:
        pretty = info.os_release.get("PRETTY_NAME") or info.os_release.get("NAME") or ""
        print("linux:")
        if pretty:
            print(f"  os-release: {pretty}")
        if info.os_release.get("VERSION_ID"):
            print(f"  version_id: {info.os_release.get('VERSION_ID')}")
        if info.etc_version:
            print(f"  /etc/version: {info.etc_version}")
        if info.etc_timestamp:
            print(f"  /etc/timestamp: {info.etc_timestamp}")

    if info.nested_archives:
        print("nested archives:")
        for n in info.nested_archives:
            print(f"  {n}")

    if info.warnings:
        print("warnings:")
        for w in info.warnings:
            print(f"  {w}")

    if verbose:
        print(f"header hex: {info.header_hex}")


def write_json(infos: list[ZnxInfo], path: Path) -> None:
    def conv(o: Any) -> Any:
        if isinstance(o, ZnxInfo):
            d = asdict(o)
            return d
        if isinstance(o, ZnxEntry):
            return asdict(o)
        raise TypeError(type(o).__name__)
    path.write_text(json.dumps([conv(i) for i in infos], indent=2), encoding="utf-8")


def write_csv(infos: list[ZnxInfo], path: Path) -> None:
    fields = [
        "znx_file", "znx_size", "header_total_minus_0x1c",
        "entry_index", "entry_name", "payload_offset", "stored_offset", "size",
        "mystery", "crc32", "sha256",
        "os_pretty", "os_name", "os_version_id", "etc_version", "etc_timestamp",
        "nested_archives", "warnings",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for info in infos:
            osr = info.os_release
            for e in info.entries:
                w.writerow({
                    "znx_file": info.file,
                    "znx_size": info.size,
                    "header_total_minus_0x1c": info.header_total_minus_0x1c,
                    "entry_index": e.index,
                    "entry_name": e.name,
                    "payload_offset": f"0x{e.payload_offset:x}",
                    "stored_offset": f"0x{e.stored_offset:x}",
                    "size": e.size,
                    "mystery": f"0x{e.mystery:08x}",
                    "crc32": e.crc32,
                    "sha256": e.sha256,
                    "os_pretty": osr.get("PRETTY_NAME", ""),
                    "os_name": osr.get("NAME", ""),
                    "os_version_id": osr.get("VERSION_ID", ""),
                    "etc_version": info.etc_version,
                    "etc_timestamp": info.etc_timestamp,
                    "nested_archives": " | ".join(info.nested_archives),
                    "warnings": " | ".join(info.warnings),
                })


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Inspect IDEC ZNX package structure and embedded Linux package inventory.")
    ap.add_argument("znx", nargs="+", help="ZNX file(s) to inspect")
    ap.add_argument("--csv", dest="csv_path", help="write member-level CSV report")
    ap.add_argument("--json", dest="json_path", help="write full JSON report")
    ap.add_argument("--no-nested", action="store_true", help="do not inspect tar.xz members for nested package names")
    ap.add_argument("--no-hash", action="store_true", help="skip SHA256/CRC32 of top-level members")
    ap.add_argument("-v", "--verbose", action="store_true", help="print raw header hex")
    args = ap.parse_args(argv)

    infos: list[ZnxInfo] = []
    rc = 0
    for item in args.znx:
        path = Path(item)
        try:
            info = build_info(path, nested=not args.no_nested, hash_members=not args.no_hash)
            infos.append(info)
            print_info(info, verbose=args.verbose)
        except Exception as e:
            rc = 1
            print(f"{item}: ERROR: {e}", file=sys.stderr)

    if args.csv_path and infos:
        write_csv(infos, Path(args.csv_path))
        print(f"\nwrote CSV: {args.csv_path}")
    if args.json_path and infos:
        write_json(infos, Path(args.json_path))
        print(f"wrote JSON: {args.json_path}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
