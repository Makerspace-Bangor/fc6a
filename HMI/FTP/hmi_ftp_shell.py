#!/usr/bin/env python3
import errno
import socket
import random
import time
import os
from ftplib import FTP, all_errors
import argparse
import subprocess
from ftplib import FTP, all_errors, error_perm

DEFAULT_HMI_IP = "192.168.1.150"
HMI_IP = DEFAULT_HMI_IP
DISM_PORT = 2537
FTP_PORT = 2539
FTP_STARTED = 0.0 # debug timer
LAST_CMD    = 0.0 # debug timer
"""
OK tried a bunch of things. 
NOOP ( keep alive )did not help.
setting ftp to active might address some issues, but failed to fix all.
tried caching, marginal help.
FTP_STARTED = time.monotonic()
ftp.set_debuglevel(2) # max detail debug log

./hmi_ftp_shell.py 192.168.1.20 --debug
"""

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
    if not rx:
        raise ConnectionError(f"HMI closed while waiting for cmd {name}")

    print(f"{name} RX:", rx.hex(" "))
    return rx


def open_hmi_ftp_session(username, password):
    with socket.create_connection((HMI_IP, DISM_PORT), timeout=20) as s:
        send_cmd(s, 5, b"00FFAB", "AB")
        send_cmd(s, 6, make_lb_body(username, password), "LB")
        send_cmd(s, 7, b"00FFLF", "LF")


def wait_for_ftp(username, password, debug=False):
    last = None

    for attempt in range(1, 21):
        try:
            ftp = FTP()
            ftp.connect(HMI_IP, FTP_PORT, timeout=20)
            print(ftp.getwelcome())
            ftp.login(username, password)
            if debug:
                ftp.set_debuglevel(2) # max debug

            #ftp.set_pasv(False) # pasv default, if false, set to active mode
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

            elif cmd in ("h", "help", "?"):
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

            elif cmd in ("ls", "dir"):
                path = args[0] if args else ""
                ftp.retrlines(f"LIST {path}".strip())

            elif cmd == "nlst":
                path = args[0] if args else ""
                for name in ftp.nlst(path):
                    print(name)

            elif cmd == "cd":
                ftp.cwd(args[0])
                ftp.retrlines("LIST")

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
            print(f"ERR {type(e).__name__}: {e!r}")


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
    
    parser.add_argument(
        "-fz",
        "--filezilla",
        action="store_true",
        help="Open FileZilla instead of the interactive FTP shell"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable FTP protocol debugging"
    )

    
    args = parser.parse_args()

    HMI_IP = args.ip

    # Generate user creds   
    username = rand_hex(16)
    password = rand_hex(15)


    #open_hmi_ftp_session(username, password)
    #ftp = wait_for_ftp(username, password)
    # Gracefull close
    try:
        open_hmi_ftp_session(username, password)
    except OSError as e:
        if e.errno in (errno.EHOSTUNREACH, errno.ENETUNREACH):
            print(f"No route to host: Check IP address. Default is: {HMI_IP}")
        elif e.errno == errno.ECONNREFUSED:
            print(f"Connection refused: No HMI at {HMI_IP}:{DISM_PORT}")
        elif e.errno == errno.ETIMEDOUT:
            print(f"Connection timed out: Check IP address {HMI_IP}")
        else:
            print(f"Connection failed: {e}")
        return 1

    ftp = wait_for_ftp(username, password, args.debug)

    if args.filezilla:
        ftp.quit()  # release the connection for FileZilla

        subprocess.Popen([
            "filezilla",
            f"ftp://{username}:{password}@{HMI_IP}:{FTP_PORT}/"
        ])

        print("Opened FileZilla.")
        return

    print(f"\nHMI: {HMI_IP}\n") 
    print("Temporary FTP creds:")
    print("USER", username)
    print("PASS", password)

    ftp.retrlines("LIST")
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
    raise SystemExit(main())
