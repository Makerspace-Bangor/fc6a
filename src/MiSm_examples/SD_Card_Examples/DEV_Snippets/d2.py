#!/usr/bin/env python3
import argparse
import re
import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 9600


def bcc_xor(data: bytes) -> bytes:
    b = 0
    for x in data:
        b ^= x
    return f"{b:02X}".encode("ascii")


def frame_bcc(body: bytes) -> bytes:
    msg = b"\x05" + body
    return msg + bcc_xor(msg) + b"\r"


def frame_no_bcc(body: bytes) -> bytes:
    return b"\x05" + body + b"\r"


def printable(data: bytes) -> str:
    out = []
    for b in data:
        if 32 <= b <= 126:
            out.append(chr(b))
        elif b == 0x00:
            out.append("<NUL>")
        elif b == 0x05:
            out.append("<ENQ>")
        elif b == 0x06:
            out.append("<ACK>")
        elif b == 0x15:
            out.append("<NAK>")
        elif b == 0x0D:
            out.append("<CR>")
        else:
            out.append(f"<{b:02X}>")
    return "".join(out)


def recv_until_cr(ser, timeout=2.0, limit=4096) -> bytes:
    end = time.time() + timeout
    buf = bytearray()

    while time.time() < end and len(buf) < limit:
        b = ser.read(1)
        if not b:
            continue
        buf += b
        if b == b"\r":
            break

    return bytes(buf)


def strip_reply(rx: bytes) -> bytes:
    if rx and rx[0] in (0x06, 0x15) and len(rx) >= 6:
        return rx[4:-3]
    return b""


def sd_open_body(path: str) -> bytes:
    path = "/" + path.strip("/")
    p = path.encode("ascii") + b"\x00"
    return b"FF1FR" + f"{len(p):03X}".encode("ascii") + p


def sd_delete_body(path: str) -> bytes:
    path = "/" + path.strip("/")
    p = path.encode("ascii") + b"\x00"
    return b"FF0FC" + f"{len(p):03X}".encode("ascii") + p


def parse_entry(payload: bytes):
    text = payload.rstrip(b"\x00").decode("ascii", errors="replace")

    m = re.match(
        r"^([01])([0-9A-Fa-f]{8})([0-9]{8})([0-9]{6})([0-9A-Fa-f]{3})(.*)$",
        text,
    )
    if not m:
        return None

    kind, size_hex, date, tm, name_len_hex, name = m.groups()
    name_len = int(name_len_hex, 16) - 1
    name = name[:name_len]

    return {
        "is_dir": kind == "1",
        "size": int(size_hex, 16),
        "date": date,
        "time": tm,
        "name": name,
        "raw": text,
    }


def list_dir(ser, path: str, debug=False):
    path = "/" + path.strip("/")
    ser.reset_input_buffer()

    pkt = frame_bcc(sd_open_body(path))

    if debug:
        print("TX list:", printable(pkt))

    ser.write(pkt)
    ser.flush()

    rx = recv_until_cr(ser)
    payload = strip_reply(rx)

    if debug:
        print("RX:", printable(rx))
        print("DATA:", printable(payload))

    count = int(payload.decode("ascii"), 16)
    entries = []

    for i in range(count):
        body = b"FF0FR21" if i == count - 1 else b"FF1FR20"
        pkt = frame_no_bcc(body)

        if debug:
            print("TX entry:", printable(pkt))

        ser.write(pkt)
        ser.flush()

        rx = recv_until_cr(ser)
        payload = strip_reply(rx)
        entry = parse_entry(payload)

        if debug:
            print("RX:", printable(rx))
            print("ENTRY:", entry)

        if entry:
            entries.append(entry)

    return entries


def delete_path(ser, path: str, debug=False):
    pkt = frame_bcc(sd_delete_body(path))

    if debug:
        print()
        print("TX delete:", printable(pkt))

    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()

    rx = recv_until_cr(ser)
    payload = strip_reply(rx)

    if debug:
        print("RX:", printable(rx))
        print("DATA:", printable(payload))

    return rx.startswith(b"\x06")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--folder", default="/FCDATA01/DATALOG/1-secLog/DETZ")
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--allow-dir", action="store_true")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    with serial.Serial(
        args.port,
        args.baud,
        bytesize=serial.SEVENBITS,
        parity=serial.PARITY_EVEN,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05,
        write_timeout=1.0,
    ) as ser:
        time.sleep(0.5)

        entries = list_dir(ser, args.folder, debug=args.debug)

        print(args.folder.rstrip("/") + "/")
        for e in entries:
            tag = "DIR " if e["is_dir"] else "FILE"
            size = "" if e["is_dir"] else f" {e['size']} bytes"
            print(f"  {tag} {e['name']}{'/' if e['is_dir'] else ''}{size}")

        if not args.file:
            print()
            print("No files requested for delete.")
            print("Example:")
            print(f"  ./delete_file.py {args.port} --folder {args.folder} --file some.csv --yes")
            return

        by_name = {e["name"]: e for e in entries}

        for filename in args.file:
            if filename not in by_name:
                print(f"not found: {filename}")
                continue

            e = by_name[filename]

            if e["is_dir"] and not args.allow_dir:
                print(f"refusing directory without --allow-dir: {filename}")
                continue

            full_path = args.folder.rstrip("/") + "/" + filename

            if not args.yes:
                print(f"dry-run delete: {full_path}")
                continue

            ok = delete_path(ser, full_path, debug=args.debug)
            print(("deleted: " if ok else "delete failed: ") + full_path)


if __name__ == "__main__":
    main()
