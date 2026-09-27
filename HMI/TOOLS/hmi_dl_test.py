#!/usr/bin/env python3

import argparse
import socket
import time

IP = "192.168.1.150"
PORT = 2537

HEADER = bytes.fromhex(
    "01 00 00 00 00 01 00 00 00 00 00 00 00 00 00 01 01 01"
)


def make_packet(command, data=""):
    inner = b"\x0500FF" + command.encode("ascii") + data.encode("ascii")

    checksum = 0
    for byte in inner:
        checksum ^= byte

    inner += f"{checksum:02X}".encode("ascii") + b"\r"

    packet = bytearray(HEADER)
    packet[2:4] = (len(packet) + len(inner)).to_bytes(2, "big")

    return bytes(packet) + inner


def recv_exact(sock, size):
    data = bytearray()

    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise ConnectionError("HMI closed connection")
        data.extend(chunk)

    return bytes(data)


def transact(ip, port, command, data=""):
    packet = make_packet(command, data)

    print(f"\nCommand: {command} {data}")
    print(f"TX: {packet.hex(' ')}")

    with socket.create_connection((ip, port), timeout=5) as sock:
        sock.settimeout(5)
        sock.sendall(packet)

        header = recv_exact(sock, 4)
        length = int.from_bytes(header[2:4], "big")

        if not 18 <= length <= 4096:
            raise ValueError(f"Invalid packet length: {length}")

        response = header + recv_exact(sock, length - 4)

    print(f"RX: {response.hex(' ')}")

    payload = response[18:]
    print(f"Payload: {payload.decode('ascii', errors='replace')!r}")

    return payload


def get_screen(ip, port):
    payload = transact(ip, port, "DM")

    if not payload or payload[0] != 0x02:
        print("DM did not return screen data")
        return None

    try:
        data = payload[5:29].decode("ascii")

        if len(data) != 24:
            raise ValueError("Unexpected screen data length")

        screen = int(data[:4], 16)
        overlays = [
            int(data[i:i + 4], 16)
            for i in range(4, 24, 4)
        ]

        print(f"Current screen: {screen}")
        print(f"Overlay screens: {overlays}")

        return screen

    except (ValueError, UnicodeDecodeError) as exc:
        print(f"Screen decode error: {exc}")
        return None


def change_screen(ip, port, screen):
    payload = transact(ip, port, "DL", f"{screen:04X}")

    if not payload:
        print("No DL response")
        return False

    if payload[0] == 0x06:
        print("DL: ACK")
        return True

    if payload[0] == 0x15:
        print("DL: NAK")

        if len(payload) >= 7:
            error = payload[5:7].decode("ascii", errors="replace")
            print(f"Error code: {error}")

        return False

    print("Unexpected DL response")
    return False


def main():
    parser = argparse.ArgumentParser(description="IDEC HMI screen change test")
    parser.add_argument("--ip", default=IP)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--screen", type=int, default=2)
    args = parser.parse_args()

    if not 0 <= args.screen <= 65535:
        parser.error("Screen number must be between 0 and 65535")

    print("Reading current screen...")
    original = get_screen(args.ip, args.port)

    if original is None:
        print("Aborting: initial DM query failed")
        return

    print(f"\nRequesting screen {args.screen}...")
    accepted = False

    try:
        accepted = change_screen(args.ip, args.port, args.screen)
    except (OSError, ValueError) as exc:
        print(f"DL communication error: {exc}")

    time.sleep(0.5)

    print("\nReading screen after DL...")
    current = get_screen(args.ip, args.port)

    print("\n--- RESULT ---")
    print(f"Original screen: {original}")
    print(f"Requested screen: {args.screen}")
    print(f"Current screen: {current}")
    print(f"DL acknowledged: {accepted}")

    if accepted and current == args.screen:
        print("DL acknowledged; requested screen is active")
    elif not accepted:
        print("DL rejected; no successful screen change verified")
    elif current is None:
        print("DL acknowledged, but screen could not be verified")
    else:
        print("DL acknowledged, but requested screen is not active")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}")
