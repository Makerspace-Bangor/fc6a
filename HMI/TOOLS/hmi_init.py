#!/usr/bin/env python3

import socket
import argparse
"""
Your PC, arduino, or other device needs to have the IP the 
HMI is looking for to have the init_hmi.py initialize a connection.
Change as needed:

HMI Multicast packet:
192.168.1.150:54754 -> 192.168.1.255:5150
payload: 31 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00

$ sudo ip addr flush dev enp2s0
$ sudo ip addr add 192.168.1.160/24 dev enp2s0
$ sudo ip link set enp2s0 up
$ python3 hmi_init.py --host 0.0.0.0 --port 2101

The exact registers the HMI requires seems to vary. 
I havent worked out what those are exactly yet. 
it might be as simple as defining a READ to a register 
you plan on providing. 

"""

HOST = "0.0.0.0"
PORT = 2357

def xor_bcc(data):
    b = 0
    for c in data:
        b ^= c
    return b


def read_d(addr):
    if addr == 570:
        return 26

    if addr in (3498, 3499, 3500):
        return 0

    return 0


def make_reply_rd(addr, nbytes):

    words = nbytes // 2
    body = bytearray()
    body.append(0x06)      # ACK
    body += b"000"         # Device 00, Status 0

    for i in range(words):
        body += f"{read_d(addr+i):04X}".encode()

    bcc = xor_bcc(body)
    body += f"{bcc:02X}".encode()
    body += b"\r"

    return bytes(body)


def make_reply_r_():

    body = bytearray()
    body.append(0x06)      # ACK
    body += b"000"

    # one word of timer information
    body += b"0000"
    bcc = xor_bcc(body)
    body += f"{bcc:02X}".encode()
    body += b"\r"

    return bytes(body)


def handle(sock):

    buf = b""
    while True:
        c = sock.recv(1)

        if not c:
            break

        buf += c

        if c != b"\r":
            continue

        print()
        print("RX HEX:  ", " ".join(f"{b:02X}" for b in buf))
        print("RX ASCII:", repr(buf))

        if len(buf) >= 14 and buf[0] == 0x05:

            cmd = buf[4:6]

            print("Command:", cmd.decode(errors="replace"))
            print("Payload:", buf[6:-3].decode(errors="replace"))
            print("BCC:", buf[-3:-1].decode())

            # Read D registers
            if cmd == b"RD":

                addr = int(buf[6:10])
                nbytes = int(buf[10:12], 16)
                print(f"READ D{addr} ({nbytes//2} words)")
                reply = make_reply_rd(addr, nbytes)
                print("TX:", reply)
                sock.sendall(reply)

            elif cmd == b"RM":
                nbytes = int(buf[10:12], 16)
                reply = b"\x06000" + (b"0" * (nbytes * 8))
                reply += f"{xor_bcc(reply):02X}".encode() + b"\r"
                sock.sendall(reply)

            elif cmd.startswith(b"R"):
                dtype = cmd[1:2].decode(errors="replace")
                addr = int(buf[6:10])
                nbytes = int(buf[10:12], 16)
                print(f"GENERIC READ {dtype}{addr} ({nbytes} bytes)")
                body = bytearray()
                body.append(0x06)
                body += b"000"
                body += b"00" * nbytes   # nbytes of zero data, ASCII hex

                bcc = xor_bcc(body)
                body += f"{bcc:02X}".encode()
                body += b"\r"

                print("TX:", bytes(body))
                sock.sendall(bytes(body))

            # Read timer info (R_)
            elif cmd == b"R_":
                print("READ TIMER INFO")
                reply = make_reply_r_()
                print("TX:", reply)
                sock.sendall(reply)
            else:
                print("Unhandled command:", cmd)
        buf = b""


def main():

    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", default=PORT, type=int)
    args = ap.parse_args()

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((args.host, args.port))
    s.listen(1)

    print(f"Listening on {args.host}:{args.port}")
    while True:

        client, addr = s.accept()
        print("\nConnected:", addr)

        try:
            handle(client)
        finally:
            client.close()
            print("Disconnected")


if __name__ == "__main__":
    main()
