#!/usr/bin/env python3
"""
Extract/list top-level files from an IDEC HMI .ZNX package.

Examples:
    ./extract_znx.py Read_regs.ZNX
    ./extract_znx.py unpack Read_regs.ZNX
    ./extract_znx.py extract Read_regs.ZNX -o out_dir
    ./extract_znx.py list Read_regs.ZNX
    ./extract_znx.py -l Read_regs.ZNX

Output defaults to a folder named after the input basename, e.g. Read_regs/.
This script does NOT unpack inner .tar.xz/.xz/.znv files; it only writes the
archive members stored by the ZNX container.
"""

from __future__ import annotations

import argparse
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ZNX_MAGIC = b"ZNX\x00"
LOCAL_HEADER_LEN = 0x1C
DIR_START = 0x1C
MIN_ENTRY_LEN = 20
SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._+@%=-]+$")


@dataclass(frozen=True)
class ZnxEntry:
    name: str
    table_offset: int
    member_id: int
    stored_offset: int
    payload_offset: int
    size: int
    checksum_or_id: int

    @property
    def end(self) -> int:
        return self.payload_offset + self.size


def u32le(buf: bytes, off: int) -> int:
    return struct.unpack_from("<I", buf, off)[0]


def clean_member_name(raw: bytes) -> str | None:
    """Return a safe basename from a NUL-padded ASCII filename field."""
    raw = raw.split(b"\x00", 1)[0]
    if not raw:
        return None
    try:
        name = raw.decode("ascii")
    except UnicodeDecodeError:
        return None

    # Keep this extractor boring and safe: no paths, no traversal.
    if "/" in name or "\\" in name or name in {".", ".."}:
        return None
    if not SAFE_NAME_RE.match(name):
        return None
    if "." not in name:
        return None
    return name


def iter_directory_entries(data: bytes) -> Iterable[ZnxEntry]:
    """
    Parse the ZNX directory table observed in NV4-generated ZNX packages.

    Directory row layout, little-endian:
        +0x00 u32 member id / type
        +0x04 u32 stored offset
        +0x08 u32 payload size
        +0x0c u32 checksum/id/unknown
        +0x10 u32 filename field length
        +0x14 char filename[N], N includes NUL/padding

    The actual file payload starts at:
        stored_offset + 0x1c

    In the sample:
        os_update.tar.xz: stored 0x48       payload 0x64
        project.znv:      stored 0x26bb5c4  payload 0x26bb5e0
    """
    n = len(data)
    off = DIR_START

    while off + MIN_ENTRY_LEN <= n:
        member_id = u32le(data, off)
        stored = u32le(data, off + 4)
        size = u32le(data, off + 8)
        chk = u32le(data, off + 12)
        name_len = u32le(data, off + 16)

        if name_len == 0 or name_len > 512:
            break
        if off + MIN_ENTRY_LEN + name_len > n:
            break

        raw_name = data[off + MIN_ENTRY_LEN : off + MIN_ENTRY_LEN + name_len]
        name = clean_member_name(raw_name)
        if not name:
            break

        payload_off = stored + LOCAL_HEADER_LEN
        if payload_off + size > n:
            raise ValueError(
                f"directory entry {name!r} points outside file: "
                f"payload=0x{payload_off:x}, size=0x{size:x}, file=0x{n:x}"
            )

        yield ZnxEntry(
            name=name,
            table_offset=off,
            member_id=member_id,
            stored_offset=stored,
            payload_offset=payload_off,
            size=size,
            checksum_or_id=chk,
        )

        off += MIN_ENTRY_LEN + name_len


def default_out_dir(src: Path) -> Path:
    if src.name.lower().endswith(".znx"):
        return src.with_name(src.name[:-4])
    return src.with_name(src.stem)


def print_entries(entries: list[ZnxEntry]) -> None:
    print(f"found {len(entries)} file(s)\n")
    print(f"{'offset':>12}  {'size':>12}  {'stored':>12}  name")
    print(f"{'-' * 12}  {'-' * 12}  {'-' * 12}  {'-' * 32}")
    for e in entries:
        print(f"0x{e.payload_offset:08x}  0x{e.size:08x}  0x{e.stored_offset:08x}  {e.name}")


def extract_entries(src: Path, out_dir: Path, entries: list[ZnxEntry], overwrite: bool) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    with src.open("rb") as f:
        for e in entries:
            dst = out_dir / e.name
            if dst.exists() and not overwrite:
                raise FileExistsError(f"refusing to overwrite existing file: {dst}  (use -f)")

            f.seek(e.payload_offset)
            remaining = e.size
            with dst.open("wb") as out:
                while remaining:
                    chunk = f.read(min(1024 * 1024, remaining))
                    if not chunk:
                        raise IOError(f"unexpected EOF while extracting {e.name}")
                    out.write(chunk)
                    remaining -= len(chunk)


def normalize_legacy_argv(argv: list[str]) -> tuple[str, list[str]]:
    """
    Support both styles:
        extract_znx.py Read_regs.ZNX
        extract_znx.py unpack Read_regs.ZNX
        extract_znx.py list Read_regs.ZNX
    """
    if argv and argv[0] in {"unpack", "extract", "x"}:
        return "extract", argv[1:]
    if argv and argv[0] in {"list", "ls"}:
        return "list", argv[1:]
    return "auto", argv


def main(argv: list[str]) -> int:
    mode, argv = normalize_legacy_argv(argv)

    ap = argparse.ArgumentParser(description="Extract files from an IDEC HMI ZNX archive")
    ap.add_argument("znx", type=Path, help="input .ZNX file")
    ap.add_argument("-o", "--out", type=Path, help="output folder; default: input basename")
    ap.add_argument("-l", "--list", action="store_true", help="list archive contents only")
    ap.add_argument("-f", "--force", action="store_true", help="overwrite existing output files")
    args = ap.parse_args(argv)

    if mode == "list":
        args.list = True

    src = args.znx
    if not src.exists():
        print(f"error: file not found: {src}", file=sys.stderr)
        return 2

    data = src.read_bytes()
    if not data.startswith(ZNX_MAGIC):
        print(f"error: {src} does not start with ZNX magic", file=sys.stderr)
        return 3

    try:
        entries = list(iter_directory_entries(data))
    except Exception as exc:
        print(f"error: failed to parse ZNX directory: {exc}", file=sys.stderr)
        return 4

    if not entries:
        print("error: no ZNX directory entries found", file=sys.stderr)
        return 5

    print_entries(entries)

    if args.list:
        return 0

    out_dir = args.out if args.out else default_out_dir(src)
    try:
        extract_entries(src, out_dir, entries, overwrite=args.force)
    except Exception as exc:
        print(f"\nerror: {exc}", file=sys.stderr)
        return 6

    print(f"\nextracted {len(entries)} file(s) to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
