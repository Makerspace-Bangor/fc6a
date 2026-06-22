#!/usr/bin/env python3
import argparse
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


def delete_body(path: str) -> bytes:
    path = "/" + path.strip("/")
    path_bytes = path.encode("ascii") + b"\x00"
    length = len(path_bytes)
    return b"FF0FC" + f"{length:03X}".encode("ascii") + path_bytes


def delete_path(ser, path: str, debug=False) -> bool:
    body = delete_body(path)
    pkt = frame_bcc(body)

    if debug:
        print()
        print("TX delete:", path)
        print("TX hex   :", pkt.hex(" ").upper())
        print("TX txt   :", printable(pkt))

    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()

    rx = recv_until_cr(ser)
    data = strip_reply(rx)

    if debug:
        print("RX hex   :", rx.hex(" ").upper() if rx else "")
        print("RX txt   :", printable(rx) if rx else "")
        print("DATA     :", printable(data))

    if rx.startswith(b"\x06"):
        print(f"deleted or accepted: {path}")
        return True

    print(f"delete failed: {path}")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument(
        "paths",
        nargs="*",
        default=[
            "/FCDATA01/DATALOG/1-secLog/20260406",
            "/FCDATA01/DATALOG/1-secLog/20260407",
            "/FCDATA01/DATALOG/1-secLog/LULZ",
        ],
    )
    args = ap.parse_args()

    print("Paths to delete:")
    for p in args.paths:
        print(" ", p)

    if not args.yes:
        print()
        print("Dry run only. Add --yes to actually delete.")
        return

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

        for path in args.paths:
            delete_path(ser, path, debug=args.debug)
            time.sleep(0.1)


if __name__ == "__main__":
    main()
'''
listing specified folders from SD Card in IDEC PLC.
SD Card Read differs from Maintenance protocol standard command structure in that:
There is no ENQ, and no BCC when asking for a listing.
The Delete command however :
ENQ FF0FC <LEN> <PATH> NUL BCC CR


Paths are not returned initialy, instead you get a count of files in the path specified.
So then you read the entries by reading the number of entries with the FF1FR20
command, which is basicly a list command. 
((There is a timeout, I havent worked out what it is exactly, think 500ms))

Each reply from FF1FR20 contains 1 entry. 
#Folder Example:
1000000002026040618334200920260406

1         = type folder
00000000  = size
20260406  = date
183342    = time
009       = name length
20260406  = name

#For Files:
Example:
00002D6D452026040700000401020260406_00.csv
0         = type file
0002D6D4  = size
20260407  = date
000004    = time
010       = name length
20260406_00.csv  = file name

These are my current thoughts, and it seems to be working.
((I Could be confussed though, all of this was confussing.
  There is what I just called name length, could be the itteration number, 
  and I have an off by one type scenario ))

So then, the delete command:
FF      Device
0       Continuation/end
FC      File/Folder delete command
LEN     3-digit hex path length
PATH    Full SD path
NUL     0x00 terminator
BCC     XOR checksum
CR      0x0D

ENQ FF0FC <LEN> <PATH> NUL BCC CR

The working flow is:
opendir()  -> FR
readdir()  -> FR20
closedir() -> FR21

remove() / rmdir() -> FC

Closedir() FR21:
Failing to close a directory may result in the PLC being unable to read,
but unseatig the SD Card, or just waiting, seems to resolve this. Successive reads
as part of some program may fail though.  


FC Removes Files, and folders, and the files in the folder if only the folder is specified. 
FF0FC<len><path><NUL>

'''
