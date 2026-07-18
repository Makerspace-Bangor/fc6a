#!/usr/bin/env python3
import argparse
import time
import serial

PORT = "/dev/ttyACM0"
BAUD = 9600

DEFAULT_FILE = "/FCDATA01/DATALOG/1-secLog/LOG_260609.CSV"
DEFAULT_OUT = "LOG_260608.CSV"
BLOCK_HEX = "5C0"  # 0x5C0 = 1472 bytes


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


def recv_until_cr(ser, timeout=3.0, limit=4096) -> bytes:
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


def open_file_body(path: str, block_hex: str = BLOCK_HEX) -> bytes:
    path = "/" + path.strip("/")
    p = path.encode("ascii") + b"\x00"
    length = f"{len(p):03X}".encode("ascii")
    return b"FF1Fu" + length + p + block_hex.encode("ascii")


''' 
Something here isnt quite right. 
Extraneous 0's in line 67 time stamp, 
but everything ive tried is worse. 
its really close. 
'''

def strip_download_payload(rx: bytes) -> bytes:
    """
    Expected reply:
      ACK FF 1 <block_len_hex_3> <data> BCC CR

    Header:
      06 FF 1 5 C 0 ...
      bytes 0..5 are ACK/device/continuation/block length.
    Trailer:
      last 3 bytes are BCC_hi BCC_lo CR.
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


def download_file(ser, plc_path: str, out_path: str, expected_size=None, debug=False):
    ser.reset_input_buffer()

    open_pkt = frame_bcc(open_file_body(plc_path))

    if debug:
        print("TX open hex:", open_pkt.hex(" ").upper())
        print("TX open txt:", printable(open_pkt))

    ser.write(open_pkt)
    ser.flush()

    rx = recv_until_cr(ser, timeout=3.0, limit=8192)

    if debug:
        print("RX open hex:", rx.hex(" ").upper() if rx else "")
        print("RX open txt:", printable(rx) if rx else "")

    if not rx or rx[0] != 0x06:
        raise RuntimeError("Open file did not ACK")

    data = bytearray()
    first_payload = strip_download_payload(rx)

    if first_payload:
        data += first_payload
        print(f"received first block: {len(first_payload)} bytes")

    block_count = 1 if first_payload else 0

    while True:
        if expected_size is not None and len(data) >= expected_size:
            data = data[:expected_size]
            break

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
            print("RX next txt:", printable(rx[:80]) if rx else "")

        if not rx:
            print("no more reply")
            break

        if rx[0] == 0x15:
            print("NAK received")
            break

        if rx[0] != 0x06:
            print("unexpected reply:", printable(rx))
            break

        payload = strip_download_payload(rx)
        blen = get_reply_block_len(rx)

        if not payload:
            print("empty payload")
            break

        data += payload
        block_count += 1

        print(f"block {block_count}: reply_len={blen} payload={len(payload)} total={len(data)}")

        # likely final short block
        if expected_size is None and blen is not None and blen < int(BLOCK_HEX, 16):
            break

    # Try close/finalize. Not proven, but likely harmless no-BCC continuation style.
    try:
        ser.write(frame_no_bcc(b"FF0FU28"))
        ser.flush()
        recv_until_cr(ser, timeout=0.5)
    except Exception:
        pass

    with open(out_path, "wb") as f:
        f.write(data)

    print()
    print(f"saved {len(data)} bytes to {out_path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("-o", "--out", default=DEFAULT_OUT)
    ap.add_argument("--size", type=int, default=218617)
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
'''  
Example:
$./rd_file.py /dev/ttyACM0 --file /FCDATA01/DATALOG/1-secLog/20260406/20260406_00.CSV -o bleh.CSV

## Might not init properly, or maybe its timing...
$ ./rd_file.py 
Traceback (most recent call last):
  File "/home/l/Desktop/plcSD/./rd_file.py", line 233, in <module>
    main()
  File "/home/l/Desktop/plcSD/./rd_file.py", line 223, in main
    download_file(
  File "/home/l/Desktop/plcSD/./rd_file.py", line 128, in download_file
    raise RuntimeError("Open file did not ACK")
RuntimeError: Open file did not ACK

Try again basicly. 
reads files (upload to PC, aka download by any other definition)

'''
