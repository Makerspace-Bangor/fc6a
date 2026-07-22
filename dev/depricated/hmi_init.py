#!/usr/bin/env python3
import argparse
import socket
import sys
"""
Your PC, arduino, PLCs or other device need to have the IP the 
HMI is looking for to have the init_hmi.py initialize a connection.
Change as needed:

HMI Multicast packet:
192.168.1.150:54754 -> 192.168.1.255:5150
payload: 31 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00

$ sudo ip addr flush dev enp2s0
$ sudo ip addr add 192.168.1.160/24 dev enp2s0
$ sudo ip link set enp2s0 up

$ python3 hmi_init.py --host 0.0.0.0 --port 2101

# or for debug:
$ python3 hmi_init.py --host 0.0.0.0 --port 2101 -d


The exact registers the HMI requires seems to vary. 
I havent worked out what those are exactly yet. 
it might be as simple as defining a READ to a register 
you plan on providing. 
"""


HOST = "0.0.0.0"
PORT = 2101


def xor_bcc(data):
    value = 0
    for byte in data:
        value ^= byte
    return value


def read_d(addr):
    if addr == 570:
        return 26

    if addr in (3498, 3499, 3500):
        return 0

    return 0


def make_reply_rd(addr, nbytes):
    words = nbytes // 2
    body = bytearray()
    body.append(0x06)
    body += b"000"

    for offset in range(words):
        body += f"{read_d(addr + offset):04X}".encode()

    body += f"{xor_bcc(body):02X}".encode()
    body += b"\r"
    return bytes(body)


def make_reply_r_():
    body = bytearray()
    body.append(0x06)
    body += b"000"
    body += b"0000"
    body += f"{xor_bcc(body):02X}".encode()
    body += b"\r"
    return bytes(body)


def debug_packet(label, data, enabled):
    if not enabled:
        return

    print(f"{label} HEX:   {' '.join(f'{byte:02X}' for byte in data)}")
    print(f"{label} ASCII: {data!r}")


def debug_message(enabled, message):
    if enabled:
        print(message)


def handle(sock, debug=False):
    buf = b""

    while True:
        chunk = sock.recv(1)
        if not chunk:
            return

        buf += chunk
        if chunk != b"\r":
            continue

        debug_packet("RX", buf, debug)

        if len(buf) < 14 or buf[0] != 0x05:
            debug_message(debug, f"Malformed request: {buf!r}")
            buf = b""
            continue

        cmd = buf[4:6]
        payload = buf[6:-3]
        bcc = buf[-3:-1]

        debug_message(debug, f"Command: {cmd.decode(errors='replace')}")
        debug_message(debug, f"Payload: {payload.decode(errors='replace')}")
        debug_message(debug, f"BCC: {bcc.decode(errors='replace')}")

        try:
            if cmd == b"RD":
                addr = int(buf[6:10])
                nbytes = int(buf[10:12], 16)

                debug_message(debug, f"READ D{addr:04d} ({nbytes // 2} words)")
                reply = make_reply_rd(addr, nbytes)

            elif cmd == b"RM":
                nbytes = int(buf[10:12], 16)
                reply = b"\x06000" + (b"0" * (nbytes * 8))
                reply += f"{xor_bcc(reply):02X}".encode() + b"\r"

            elif cmd == b"R_":
                debug_message(debug, "READ TIMER INFO")
                reply = make_reply_r_()

            elif cmd.startswith(b"R"):
                dtype = cmd[1:2].decode(errors="replace")
                addr = int(buf[6:10])
                nbytes = int(buf[10:12], 16)

                debug_message(
                    debug,
                    f"GENERIC READ {dtype}{addr:04d} ({nbytes} bytes)",
                )

                body = bytearray()
                body.append(0x06)
                body += b"000"
                body += b"00" * nbytes
                body += f"{xor_bcc(body):02X}".encode()
                body += b"\r"
                reply = bytes(body)

            else:
                debug_message(debug, f"Unhandled command: {cmd!r}")
                buf = b""
                continue

            debug_packet("TX", reply, debug)
            sock.sendall(reply)

        except (ValueError, IndexError) as exc:
            debug_message(debug, f"Could not parse request: {exc}")

        buf = b""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show connections and complete protocol traffic",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress the startup message",
    )

    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((args.host, args.port))
        server.listen(1)
    except OSError as exc:
        print(f"Error: cannot listen on {args.host}:{args.port}: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    if not args.quiet:
        print(f"Listening on {args.host}:{args.port}", flush=True)

    try:
        while True:
            client, addr = server.accept()

            if args.debug:
                print(f"Connected: {addr[0]}:{addr[1]}")

            try:
                handle(client, debug=args.debug)
            except (ConnectionError, OSError) as exc:
                debug_message(args.debug, f"Connection ended: {exc}")
            finally:
                client.close()

            if args.debug:
                print("Disconnected")

    except KeyboardInterrupt:
        if args.debug:
            print("\nStopped")
    finally:
        server.close()


if __name__ == "__main__":
    main()
