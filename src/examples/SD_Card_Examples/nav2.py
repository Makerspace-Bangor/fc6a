#!/usr/bin/env python3
"""List an FC6A PLC SD card over TCP using MiSmTCP and MiSmSDCard."""

import argparse

from MiSmSDCard import MiSmSDCard
from MiSmTCP import MiSmTCP


IP = "192.168.1.61"
PATH = "/FCDATA01/DATALOG/1-secLog"


def walk(sd: MiSmSDCard, path: str, recursive: bool = False, depth: int = 0) -> None:
    path = "/" + path.strip("/")
    entries = sd.listSD(path)
    indent = "  " * depth

    print(f"COUNT: {len(entries)}")
    print(f"{indent}{path}/")

    for entry in entries:
        suffix = "/" if entry["is_dir"] else ""
        size = "" if entry["is_dir"] else f"  {entry['size']} bytes"
        print(f"{indent}  {entry['name']}{suffix}{size}")

    if not recursive:
        return

    for entry in entries:
        if entry["is_dir"]:
            child = path.rstrip("/") + "/" + entry["name"]
            walk(sd, child, recursive=True, depth=depth + 1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="List an IDEC FC6A SD card over the maintenance-protocol TCP port."
    )
    parser.add_argument("ip", nargs="?", default=IP, help=f"PLC IP address, default: {IP}")
    parser.add_argument("--path", default=PATH, help=f"SD directory, default: {PATH}")
    parser.add_argument("-r", "--recursive", action="store_true")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()

    plc = MiSmTCP(args.ip)
    sd = MiSmSDCard(plc, debug=args.debug)

    try:
        walk(sd, args.path, recursive=args.recursive)
    finally:
        close = getattr(plc, "close", None)
        if callable(close):
            close()


if __name__ == "__main__":
    main()
