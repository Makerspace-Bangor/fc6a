#!/usr/bin/env python3
import socket
import argparse
import time
import sys

"""
This code only works if the HMI has no password set at the time of clear
"""


PORT = 2537
DEFAULT_IP = "192.168.1.150"

def bcc(data: bytes) -> bytes:
    x = 0
    for b in data:
        x ^= b
    return f"{x:02X}".encode()

def pkt(payload: str, seq: int = 0) -> bytes:
    body = b"\x05" + payload.encode("ascii")
    body += bcc(body) + b"\r"

    return bytes([
        0x01, 0x00, (len(body) + 18) >> 8, (len(body) + 18) & 0xff,
        0x00, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, seq & 0xff,
        0x01, 0x01, 0x01
    ]) + body

def send_cmd(ip: str, payload: str, seq: int, timeout=3.0) -> bytes:
    with socket.create_connection((ip, PORT), timeout=timeout) as s:
        s.settimeout(timeout)
        s.sendall(pkt(payload, seq))
        return s.recv(4096)

def send_cmd_open(sock: socket.socket, payload: str, seq: int) -> bytes:
    sock.sendall(pkt(payload, seq))
    return sock.recv(4096)

def check_reply(raw: bytes, label: str):
    if not raw:
        raise RuntimeError(f"{label}: no reply")

    body = raw[18:] if len(raw) > 18 else raw

    if body.startswith(b"\x06"):
        return "ACK"

    if body.startswith(b"\x02"):
        return "DATA"

    raise RuntimeError(f"{label}: unexpected reply: {raw.hex(' ')}")

def clear_all(ip: str):
    print(f"Connecting to HMI {ip}:{PORT}")

    # Session 1: product/project info, then request system mode.
    with socket.create_connection((ip, PORT), timeout=3.0) as s:
        s.settimeout(5.0)

        r = send_cmd_open(s, "00FFAB", 0)
        print("AB:", check_reply(r, "AB"))

        r = send_cmd_open(s, "00FFAD", 1)
        print("AD:", check_reply(r, "AD"))

        r = send_cmd_open(s, "00FFLA", 2)
        print("LA:", check_reply(r, "LA"))

        time.sleep(4.0)

        r = send_cmd_open(s, "00FFAA02", 3)
        print("AA02:", check_reply(r, "AA02"))

    time.sleep(1.0)

    # Session 2: clear all, then return/finish.
    with socket.create_connection((ip, PORT), timeout=3.0) as s:
        s.settimeout(10.0)

        r = send_cmd_open(s, "00FFAB", 4)
        print("AB:", check_reply(r, "AB"))

        r = send_cmd_open(s, "00FFBAFFFFFF", 5) # CLEAR ALL
        print("BAFFFFFF:", check_reply(r, "BAFFFFFF"))

        time.sleep(0.25) # wait longer for handshaking? 
        """
	The HMI will reboot here. The AH command which follows seems to be
	A handshake confirmation. Seems to work fine without it but, what I
	could do is wait for it to reboot, then send this packet. 
	Theres some unidentified UDP packets from the HMI...
	So TODO: maybe.
	
	"""
        r = send_cmd_open(s, "00FFAH", 6)  # Hand shaking?
        print("AH:", check_reply(r, "AH")) # reboots before it gets here

    print("Clear All sequence completed.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Run IDEC HMI Clear All Data sequence")
    ap.add_argument("ip", nargs="?", default=DEFAULT_IP,
                    help=f"HMI IP address, default {DEFAULT_IP}")
    ap.add_argument("--yes", action="store_true",
                    help="Actually run the destructive Clear All command")
    args = ap.parse_args()

    if not args.yes:
        print("This sends the HMI Clear All Data command.")
        print("It will delete your program, and clear your registers")
        print("-- IP address will not change")
        print("-- Doesnt errase atched USB sticks")
        print("If you want to continue, re-run with --yes")	
        sys.exit(2)

    try:
        clear_all(args.ip)
    except (socket.timeout, TimeoutError):
        print(f"ERROR: HMI unavailable or timed out at {args.ip}")
        sys.exit(1)
    except OSError as e:
        print(f"ERROR: Could not connect to {args.ip}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
