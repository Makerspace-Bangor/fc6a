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
    path_bytes = path.encode("ascii") + b"\x00"
    length = len(path_bytes)
    return b"FF1FR" + f"{length:03X}".encode("ascii") + path_bytes


def parse_entry(payload: bytes):
    payload = payload.rstrip(b"\x00")

    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError:
        return None

    m = re.match(
        r"^([01])([0-9A-Fa-f]{8})([0-9]{8})([0-9]{6})([0-9A-Fa-f]{3})(.*)$",
        text,
    )

    if not m:
        return None

    kind, size_hex, date, tm, name_len_hex, name = m.groups()
    name_len = int(name_len_hex, 16)
    name = name[:name_len]

    return {
        "is_dir": kind == "1",
        "size": int(size_hex, 16),
        "date": date,
        "time": tm,
        "name": name,
        "raw": text,
    }


def send_packet(ser, pkt: bytes, label="", debug=False) -> bytes:
    if debug:
        print()
        print("TX", label)
        print("TX hex :", pkt.hex(" ").upper())
        print("TX txt :", printable(pkt))

    ser.write(pkt)
    ser.flush()

    rx = recv_until_cr(ser)

    if debug:
        print("RX hex :", rx.hex(" ").upper() if rx else "")
        print("RX txt :", printable(rx) if rx else "")
        print("DATA   :", printable(strip_reply(rx)))

    return rx


def list_dir(ser, path: str, debug=False):
    ser.reset_input_buffer()

    open_body = sd_open_body(path)
    rx = send_packet(ser, frame_bcc(open_body), "open dir", debug)
    payload = strip_reply(rx)

    try:
        count = int(payload.decode("ascii"), 16)
    except Exception:
        print("Could not decode directory count:", printable(payload))
        return []

    print("COUNT:", count)

    entries = []

    for i in range(count):
        body = b"FF0FR21" if i == count - 1 else b"FF1FR20"
        rx = send_packet(ser, frame_no_bcc(body), f"entry {i+1}/{count}", debug)

        payload = strip_reply(rx)
        entry = parse_entry(payload)

        if entry:
            entries.append(entry)
        else:
            print("Could not parse entry:", printable(payload))

        time.sleep(0.02)

    return entries


def walk(ser, path: str, recursive=False, debug=False, depth=0):
    path = "/" + path.strip("/")
    entries = list_dir(ser, path, debug=debug)

    indent = "  " * depth
    print(f"{indent}{path}/")

    for e in entries:
        suffix = "/" if e["is_dir"] else ""
        size = "" if e["is_dir"] else f"  {e['size']} bytes"
        print(f"{indent}  {e['name']}{suffix}{size}")

    if recursive:
        for e in entries:
            if e["is_dir"]:
                walk(ser, path + "/" + e["name"], recursive=True, debug=debug, depth=depth + 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--path", default="/FCDATA01/DATALOG/1-secLog")
    ap.add_argument("-r", "--recursive", action="store_true")
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
        walk(ser, args.path, recursive=args.recursive, debug=args.debug)


if __name__ == "__main__":
    main()

'''
Open/list directory:
ENQ FF1FR <path_len_hex_3> <path> NUL BCC CR

Reply:
ACK FF0 <count_hex_4> BCC CR

Read next entry:
ENQ FF1FR20 CR
(no BCC)

Read final entry:
ENQ FF0FR21 CR
(no BCC)


## Eaxmple Usage:
$ ./nav2.py  /dev/ttyACM0 
COUNT: 31
/FCDATA01/DATALOG/1-secLog/
  20260406/
  20260407/
  20260408/
  20260409/
  20260410/
  20260411/
  20260412/
  20260413/
  20260414/
  20260415/
  20260416/
  20260417/
  20260418/
  20260419/
  20260420/
  20260501/
  20260502/
  20260503/
  20260504/
  20260505/
  20260506/
  20260507/
  20260508/
  20260509/
  20260510/
  20260512/
  20260328/
  20260607/
  DETZ/
  DERP/
  LULZ/

'''

