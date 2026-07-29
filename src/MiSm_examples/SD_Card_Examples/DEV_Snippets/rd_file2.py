#!/usr/bin/env python3
import argparse
import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 9600

DEFAULT_FILE = "/FCDATA01/DATALOG/1-secLog/LOG_260608.CSV"
DEFAULT_OUT = "LOG_260608.CSV"
DEFAULT_SIZE = 218617
BLOCK_HEX = "5C0"   # 1472 bytes


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


def recv_until_cr(ser, timeout=3.0, limit=8192) -> bytes:
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
    # Generic ACK/NAK payload stripper:
    # ACK/NAK + dev(2) + status/continuation(1) + data + BCC(2) + CR
    if rx and rx[0] in (0x06, 0x15) and len(rx) >= 6:
        return rx[4:-3]
    return b""


def strip_download_payload(rx: bytes) -> bytes:
    """
    File data block reply appears to be:

      ACK FF 1 5 C 0 <1472 bytes data> BCC CR

    Header is 6 bytes:
      06 FF 1 5 C 0

    Trailer is 3 bytes:
      BCC_hi BCC_lo CR

    NOTE:
    The open-file reply is NOT file data. Only use this on FU27 replies.
    """
    if not rx or rx[0] != 0x06:
        return b""

    if len(rx) < 9:
        return b""

    return rx[6:-3]


def get_reply_block_len(rx: bytes):
    if not rx or rx[0] != 0x06 or len(rx) < 6:
        return None

    try:
        return int(rx[3:6].decode("ascii"), 16)
    except Exception:
        return None


def open_file_body(path: str, block_hex: str = BLOCK_HEX) -> bytes:
    path = "/" + path.strip("/")
    p = path.encode("ascii") + b"\x00"
    length = f"{len(p):03X}".encode("ascii")

    # Captured form:
    # FF1Fu <LEN3> <PATH> NUL 5C0 BCC CR
    return b"FF1Fu" + length + p + block_hex.encode("ascii")


def download_file(ser, plc_path: str, out_path: str, expected_size: int, debug=False):
    ser.reset_input_buffer()

    data = bytearray()

    # 1. Open file/download session.
    open_pkt = frame_bcc(open_file_body(plc_path))

    if debug:
        print("TX open hex:", open_pkt.hex(" ").upper())
        print("TX open txt:", printable(open_pkt))

    ser.write(open_pkt)
    ser.flush()

    rx = recv_until_cr(ser, timeout=3.0, limit=8192)
    open_payload = strip_reply(rx)

    if debug:
        print("RX open hex:", rx.hex(" ").upper() if rx else "")
        print("RX open txt:", printable(rx) if rx else "")
        print("OPEN DATA  :", printable(open_payload))

    if not rx or rx[0] != 0x06:
        raise RuntimeError("Open file did not ACK")

    print("open reply:", printable(open_payload))

    # 2. Read file data blocks.
    block_count = 0

    while len(data) < expected_size:
        pkt = frame_no_bcc(b"FF1FU27")

        if debug:
            print()
            print("TX next hex:", pkt.hex(" ").upper())
            print("TX next txt:", printable(pkt))

        ser.write(pkt)
        ser.flush()

        rx = recv_until_cr(ser, timeout=3.0, limit=8192)

        if debug:
            print("RX next hex:", rx.hex(" ").upper() if rx else "")
            print("RX next txt:", printable(rx[:120]) if rx else "")

        if not rx:
            print("no more reply")
            break

        if rx[0] == 0x15:
            print("NAK received:", printable(strip_reply(rx)))
            break

        if rx[0] != 0x06:
            print("unexpected reply:", printable(rx))
            break

        payload = strip_download_payload(rx)
        blen = get_reply_block_len(rx)

        if not payload:
            print("empty payload")
            break

        remaining = expected_size - len(data)

        if len(payload) > remaining:
            payload = payload[:remaining]

        data += payload
        block_count += 1

        print(
            f"block {block_count}: "
            f"reply_len={blen} payload={len(payload)} total={len(data)}/{expected_size}"
        )

    # 3. Close/finalize. This is inferred from FU27 family.
    # If it causes trouble, comment it out.
    try:
        close_pkt = frame_no_bcc(b"FF0FU28")

        if debug:
            print()
            print("TX close hex:", close_pkt.hex(" ").upper())
            print("TX close txt:", printable(close_pkt))

        ser.write(close_pkt)
        ser.flush()
        close_rx = recv_until_cr(ser, timeout=1.0, limit=8192)

        if debug:
            print("RX close hex:", close_rx.hex(" ").upper() if close_rx else "")
            print("RX close txt:", printable(close_rx) if close_rx else "")

    except Exception:
        pass

    with open(out_path, "wb") as f:
        f.write(data)

    print()
    print(f"saved {len(data)} bytes to {out_path}")

    if len(data) != expected_size:
        print(f"WARNING: expected {expected_size} bytes")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("-o", "--out", default=DEFAULT_OUT)
    ap.add_argument("--size", type=int, default=DEFAULT_SIZE)
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
        download_file(
            ser,
            plc_path=args.file,
            out_path=args.out,
            expected_size=args.size,
            debug=args.debug,
        )


if __name__ == "__main__":
    main()
