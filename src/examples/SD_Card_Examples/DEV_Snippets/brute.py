#!/usr/bin/env python3
import argparse
import time
import serial
'''
Basicly, don't run this file. 
What I ended up with was a PLC that couldnt read the SD Card, and I was honestly probably lucky. 
I couldnt acces the SD Card again until zeroing the PLC, and reinstalling. 
but I did get a list of commands, where I could then figure out the various commands. 

Are there other unlisted commands?
theres probably a bunch of hidden commands, if you were going to look, the "R" block I know 
has Ri, RS, RN. Ri factory resets your PLC. so... avoid that.
RS sets the security bit. 
RN .. I forget.  

'''
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


def recv_until_cr(ser, timeout=2.0, limit=8192) -> bytes:
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


def path_body(cmd: bytes, path: str) -> bytes:
    path = "/" + path.strip("/")
    p = path.encode("ascii") + b"\x00"
    return b"FF1" + cmd + f"{len(p):03X}".encode("ascii") + p


def send_probe(ser, cmd: bytes, path: str, debug=False):
    body = path_body(cmd, path)
    pkt = frame_bcc(body)

    print()
    print("CMD:", cmd.decode())
    print("TX body:", printable(body))
    print("TX hex :", pkt.hex(" ").upper())

    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()

    rx = recv_until_cr(ser)
    data = strip_reply(rx)

    if rx:
        kind = "ACK" if rx[0] == 0x06 else "NAK" if rx[0] == 0x15 else "???"
    else:
        kind = "NONE"

    print("RX kind:", kind)
    print("RX hex :", rx.hex(" ").upper() if rx else "")
    print("RX txt :", printable(rx) if rx else "")
    print("DATA   :", printable(data))
    print("DATA hex:", data.hex(" ").upper())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("port", nargs="?", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument(
        "--file",
        default="/FCDATA01/DATALOG/1-secLog/DETZ/test.csv",
    )
    args = ap.parse_args()

    candidates = [
        b"FA",
        b"FB",
        # b"FC" is DELETE. Do not probe it.
        b"FD",
        b"FE",
        b"FF",
        b"FG",
        b"FH",
        b"FI",
        b"FJ",
        b"FK",
        b"FL", # This returns something, but I havent figured out its function.
        b"FM",
        b"FN",
        b"FO",
        b"FP",
        b"FQ",
        # FR is known directory list, include for comparison.
        b"FR",
        b"FS",
        b"FT",
        # b"FU", read file(number)  
        b"FV",
        b"Fa",
        b"Fb",
        b"Fc",
        b"Fd",
        b"Fe",
        b"Ff",
        b"Fg",
        b"Fh",
        b"Fi",
        b"Fj",
        b"Fk",
        b"Fl",
        b"Fm",
        b"Fn",
        b"Fo",
        b"Fp",
        b"Fq",
        b"Fr",
        b"Fs",
        b"Ft",
        b"Fu",
        b"Fv",
    ]

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

        print("File:", args.file)
        print("Skipping FC because FC deletes files/folders.")

        for cmd in candidates:
            send_probe(ser, cmd, args.file)
            time.sleep(0.15)


if __name__ == "__main__":
    main()
