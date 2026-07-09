#!/usr/bin/env python3
import socket
import argparse

PORT = 2537

def bcc(data: bytes) -> bytes:
    x = 0
    for b in data:
        x ^= b
    return f"{x:02X}".encode()

def nv4_packet(cmd: str, seq: int = 0) -> bytes:
    body = b"\x05" + cmd.encode() + bcc(b"\x05" + cmd.encode()) + b"\r"
    header = bytes([
        0x01, 0x00, 0x00, len(body) + 18,
        0x00, 0x01, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, seq & 0xff,
        0x01, 0x01, 0x01
    ])
    return header + body

def recv_all(sock, timeout=2.0):
    sock.settimeout(timeout)
    chunks = []
    while True:
        try:
            data = sock.recv(4096)
            if not data:
                break
            chunks.append(data)
            if b"</SystemInfoCDC>" in data:
                break
        except socket.timeout:
            break
    return b"".join(chunks)

def get_target_xml(ip):
    with socket.create_connection((ip, PORT), timeout=3.0) as s:
        s.sendall(nv4_packet("00FFLA", seq=0))
        raw = recv_all(s)

    start = raw.find(b"<?xml")
    end = raw.find(b"</SystemInfoCDC>")
    if start < 0 or end < 0:
        raise RuntimeError(f"XML not found. Raw reply:\n{raw.hex(' ')}")

    end += len(b"</SystemInfoCDC>")
    return raw[start:end].decode("ascii", errors="replace")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Read IDEC HMI Target Information XML"
    )
    ap.add_argument(
        "ip",
        nargs="?",
        default="192.168.1.150",
        help="HMI IP address (default: 192.168.1.150)"
    )

    args = ap.parse_args()

    try:
        print(get_target_xml(args.ip))
    except (TimeoutError, socket.timeout):
        print(f"ERROR: No response from HMI at {args.ip}")
        raise SystemExit(1)
    except ConnectionRefusedError:
        print(f"ERROR: Connection refused by {args.ip}")
        raise SystemExit(1)
    except OSError as e:
        print(f"ERROR: Unable to connect to {args.ip}: {e}")
        raise SystemExit(1)
    except Exception as e:
        print(f"ERROR: {e}")
        raise SystemExit(1)

"""
$ ./hmi_info.py 192.168.1.20
<?xml version='1.0' encoding='us-ascii'?>
<SystemInfoCDC xmlns:xsi='FTP://www.w3.org/2001/XMLSchema-instance' xmlns:xsd='FTP://www.w3.org/2001/XMLSchema'>
<date>2026/05/22 23:21:23</date>
<proj_ver>3.2.0</proj_ver>
<proj_nam>526561645F72656773</proj_nam>
<proj_exm>HGDATA01</proj_exm>
<open_Sec_Diag>0</open_Sec_Diag>
<hash>E1A3ACCC164FD17A588BD16B0686ACCFC07F12B5191AE07C2E9281833E1D9C28</hash>
<LK_cap>1024</LK_cap>
<LKR_cap>1024</LKR_cap>
<znv_ver>0.3.2</znv_ver>
<os_ver>1.2.0.0</os_ver>
<syssoft_ver>3.2.0.0</syssoft_ver>
<os_a_exsit>1</os_a_exsit>
<current_os>0</current_os>
<reset_btn>0</reset_btn>
<wlan_ip>192.168.0.150</wlan_ip>
<is_wlan>0</is_wlan>
</SystemInfoCDC>

"""
