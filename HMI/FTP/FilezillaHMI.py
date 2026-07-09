"""
TESTING ONLY for firmware uplaoding. Not For Human consumption.
Could Seriously Bork your HMI.

"""

#!/usr/bin/env python3
import socket
import random
import subprocess
import argparse
import time
from time import sleep
DISM_PORT = 2537
FTP_PORT = 2539

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

    #doubled_pass = bytes((ord(ch) * 2) & 0xff for ch in password)
    doubled_pass = "".join(ch * 2 for ch in password).encode("ascii")
    pass_field = doubled_pass.hex().encode("ascii").upper().ljust(128, b"0")

    return b"00FFLB" + bytes([0xC0, 0x00, 0x01]) + user_field + pass_field

def send_cmd(sock, seq, body, name):
    pkt = frame(seq, body)
    print(f"{name} TX:", pkt.hex(" "))
    sock.sendall(pkt)
    rx = sock.recv(4096)
    print(f"{name} RX:", rx.hex(" "))
    return rx

def open_hmi_ftp_session(ip, username, password):
    with socket.create_connection((ip, DISM_PORT), timeout=5) as s:
        send_cmd(s, 5, b"00FFAB", "AB")
        send_cmd(s, 6, b"00FFAD", "AD")
        send_cmd(s, 7, b"00FFLA", "LA")
        send_cmd(s, 8, b"00FFLE", "LE") # THIS is the Loading screen call
        send_cmd(s, 9, make_lb_body(username, password), "LB")
        sleep(2)
        send_cmd(s, 10, b"00FFLF", "LF")
        sleep(5)

"""
def open_hmi_ftp_session(ip, username, password):
    with socket.create_connection((ip, DISM_PORT), timeout=5) as s:
        send_cmd(s, 5, b"00FFAB", "AB")
        send_cmd(s, 6, make_lb_body(username, password), "LB")
        send_cmd(s, 7, b"00FFLF", "LF")
"""

def wait_for_ftp_port(ip):
    for _ in range(20):
        try:
            with socket.create_connection((ip, FTP_PORT), timeout=1):
                return True
        except OSError:
            time.sleep(0.25)
    return False

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ip", nargs="?", default="192.168.1.150")
    args = parser.parse_args()

    ip = args.ip
    username = rand_hex(16)
    password = rand_hex(15)

    print("HMI:", ip)
    print("USER:", username)
    print("PASS:", password)

    open_hmi_ftp_session(ip, username, password)

    if not wait_for_ftp_port(ip):
        print("FTP port 2539 did not open.")
        return
    #sleep(10)
    url = f"ftp://{username}:{password}@{ip}:{FTP_PORT}/"
    print("Launching:", url)

    subprocess.Popen(["filezilla", url])

if __name__ == "__main__":
    main()
