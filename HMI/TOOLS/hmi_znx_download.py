#!/usr/bin/env python3
import argparse
import hashlib
import random
import socket
import struct
import threading
import time
from ftplib import FTP, all_errors
from pathlib import Path

DEFAULT_HMI_IP = "192.168.1.150"
MAINT_PORT = 2537
FTP_PORT = 2539
"""
./hmi_znx_download.py Read_regs.ZNX --debug
./hmi_znx_download.py Read_regs.ZNX 



"""

def rand_hex(n):
    return "".join(random.choice("0123456789abcdef") for _ in range(n))


def bcc(body):
    value = 0x05
    for byte in body:
        value ^= byte
    return value


def frame(seq, body):
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


def make_lb_body(username, password):
    user_field = (
        username.encode("ascii").hex().encode("ascii").upper().ljust(64, b"0")
    )

    doubled_pass = bytes((ord(ch) * 2) & 0xff for ch in password)
    pass_field = doubled_pass.hex().encode("ascii").upper().ljust(128, b"0")

    return b"00FFLB" + bytes([0xc0, 0x00, 0x01]) + user_field + pass_field


def recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("HMI closed the maintenance connection")
        data.extend(chunk)
    return bytes(data)


def recv_frame(sock):
    first = recv_exact(sock, 4)
    total_len = int.from_bytes(first[1:4], "big")
    if total_len < 4:
        raise ValueError(f"invalid frame length {total_len}")
    return first + recv_exact(sock, total_len - 4)


def app_data(pkt):
    if len(pkt) < 19:
        return b""
    return pkt[18:]


def app_summary(pkt):
    data = app_data(pkt)
    if not data:
        return "empty"
    if data[0] == 0x06:
        return "ACK"
    if data[0] == 0x15:
        code = ""
        if len(data) >= 7:
            try:
                code = data[5:7].decode("ascii")
            except UnicodeDecodeError:
                pass
        return f"NAK {code}".rstrip()
    if data[0] == 0x02:
        try:
            end = data.index(0x03)
            return data[1:end].decode("ascii", errors="replace")
        except ValueError:
            pass
    return data[:32].hex(" ")


def parse_ab_mode(pkt):
    data = app_data(pkt)
    if not data or data[0] != 0x02:
        return None
    try:
        end = data.index(0x03)
        payload = data[1:end].decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return None
    if len(payload) < 6 or payload[0:4] != "00FF":
        return None
    try:
        return int(payload[4:6], 16)
    except ValueError:
        return None


class Maintenance:
    def __init__(self, host, debug=False):
        self.host = host
        self.debug = debug
        self.sock = None
        self.seq = 1
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.lf_thread = None

    def open(self):
        self.sock = socket.create_connection((self.host, MAINT_PORT), timeout=20)

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def next_seq(self):
        seq = self.seq
        self.seq = 1 if self.seq >= 255 else self.seq + 1
        return seq

    def command(self, body, name, timeout=20):
        with self.lock:
            old_timeout = self.sock.gettimeout()
            self.sock.settimeout(timeout)
            try:
                pkt = frame(self.next_seq(), body)
                if self.debug:
                    print(f"{name} TX:", pkt.hex(" "))

                self.sock.sendall(pkt)
                rx = recv_frame(self.sock)

                if self.debug:
                    print(f"{name} RX:", rx.hex(" "))
                else:
                    print(f"{name}: {app_summary(rx)}")

                data = app_data(rx)
                if data and data[0] == 0x15:
                    code = "??"
                    if len(data) >= 7:
                        try:
                            code = data[5:7].decode("ascii")
                        except UnicodeDecodeError:
                            pass
                    raise RuntimeError(
                        f"{name} returned NAK {code}: {data.hex(' ')}"
                    )
                return rx
            finally:
                self.sock.settimeout(old_timeout)

    def start_lf(self):
        self.stop_event.clear()
        self.lf_thread = threading.Thread(target=self._lf_loop, daemon=True)
        self.lf_thread.start()

    def _lf_loop(self):
        while not self.stop_event.is_set():
            try:
                self.command(b"00FFLF", "LF")
            except Exception as exc:
                if not self.stop_event.is_set():
                    print(f"LF warning: {exc}")
            self.stop_event.wait(5.0)

    def stop_lf(self):
        self.stop_event.set()
        if self.lf_thread is not None:
            self.lf_thread.join(timeout=10)
            self.lf_thread = None


def wait_for_ftp(host, username, password, debug=False):
    last = None

    for attempt in range(1, 21):
        try:
            ftp = FTP()
            ftp.connect(host, FTP_PORT, timeout=20)
            ftp.login(username, password)
            if debug:
                ftp.set_debuglevel(2)
            ftp.voidcmd("TYPE I")
            print(f"FTP: connected to {host}:{FTP_PORT}")
            return ftp
        except all_errors as exc:
            last = exc
            print(f"FTP attempt {attempt}/20 failed: {exc}")
            time.sleep(0.25)

    raise last


def probe_ab(host, debug=False):
    maint = Maintenance(host, debug=debug)
    try:
        maint.open()
        rx = maint.command(b"00FFAB", "AB")
        return parse_ab_mode(rx)
    finally:
        maint.close()


def wait_for_mode(host, wanted_mode, timeout=60, debug=False):
    deadline = time.monotonic() + timeout
    last_mode = None
    saw_unreachable = False

    while time.monotonic() < deadline:
        try:
            mode = probe_ab(host, debug=debug)
            last_mode = mode
            if mode == wanted_mode:
                print(f"HMI mode confirmed: {mode:02X}")
                return
        except (OSError, TimeoutError, ConnectionError):
            saw_unreachable = True

        time.sleep(0.5)

    extra = " after a temporary disconnect" if saw_unreachable else ""
    if last_mode is None:
        raise TimeoutError(
            f"HMI did not become readable in mode {wanted_mode:02X}{extra}"
        )
    raise TimeoutError(
        f"HMI stayed in mode {last_mode:02X}; "
        f"wanted {wanted_mode:02X}{extra}"
    )


def enter_system_transmission(host, maint, debug=False):
    print("Requesting System Transmission mode (AA 07)...")

    try:
        maint.command(b"00FFAA07", "AA 07", timeout=20)
    except (OSError, TimeoutError, ConnectionError) as exc:
        print(f"AA 07 connection changed during transition: {exc}")

    maint.close()

    print("Waiting for HMI to settle in System Transmission mode...")
    wait_for_mode(host, 0x07, timeout=60, debug=debug)

    maint.open()
    rx = maint.command(b"00FFAB", "AB")
    mode = parse_ab_mode(rx)
    if mode != 0x07:
        raise RuntimeError(
            f"mode changed before LE: got {mode!r}, expected 07"
        )


def file_md5(path):
    digest = hashlib.md5()
    with path.open("rb") as src:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as src:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def upload_znx(ftp, path, md5_hex):
    size = path.stat().st_size

    def progress(block):
        progress.sent += len(block)
        pct = progress.sent * 100 // size if size else 100
        if pct != progress.last:
            print(f"\rZNX upload: {pct:3d}%", end="", flush=True)
            progress.last = pct

    progress.sent = 0
    progress.last = -1

    with path.open("rb") as src:
        ftp.storbinary("STOR /tmp/os_update.znx", src, blocksize=16384,
                       callback=progress)
    print()

    md5_data = f"{md5_hex}  os_update.znx".encode("ascii")
    from io import BytesIO
    ftp.storbinary("STOR /tmp/os_update.znx.md5", BytesIO(md5_data),
                   blocksize=16384)

    print("FTP: uploaded /tmp/os_update.znx")
    print("FTP: uploaded /tmp/os_update.znx.md5")


def main():
    parser = argparse.ArgumentParser(
        description="Download an untouched ZNX to an IDEC Linux HMI"
    )
    parser.add_argument("znx", type=Path, help="vendor .ZNX file")
    parser.add_argument("--host", default=DEFAULT_HMI_IP,
                        help=f"HMI address (default: {DEFAULT_HMI_IP})")
    parser.add_argument("-y", "--yes", action="store_true",
                        help="skip the destructive-operation confirmation")
    parser.add_argument("--skip-system-transition", action="store_true",
                        help="do not force AA 07 before LE")
    parser.add_argument("--debug", action="store_true",
                        help="show maintenance and FTP protocol traffic")
    args = parser.parse_args()

    path = args.znx.expanduser().resolve()
    if not path.is_file():
        raise SystemExit(f"file not found: {path}")

    with path.open("rb") as src:
        magic = src.read(4)

    if magic[:3] != b"ZNX":
        raise SystemExit(f"{path.name}: does not start with a ZNX header")

    md5_hex = file_md5(path)
    sha256_hex = file_sha256(path)

    print(f"File:   {path}")
    print(f"Size:   {path.stat().st_size} bytes")
    print(f"MD5:    {md5_hex}")
    print(f"SHA256: {sha256_hex}")
    print(f"Target: {args.host}")
    print()
    print("Sequence:")
    if args.skip_system_transition:
        print("  AB -> LE -> LB -> LF keepalive")
    else:
        print("  AB -> AA 07 -> wait/reconnect -> AB 07 -> LE")
        print("  LB -> LF keepalive")
    print("  STOR /tmp/os_update.znx")
    print("  STOR /tmp/os_update.znx.md5")
    print("  LC Kernel -> LD -> AH")
    print()

    if not args.yes:
        answer = input("Proceed with the HMI system/OS download? [y/N] ").strip()
        if answer.lower() != "y":
            return

    username = rand_hex(16)
    password = rand_hex(15)

    maint = Maintenance(args.host, debug=args.debug)
    ftp = None
    lc_ok = False

    try:
        print("Connecting maintenance port...")
        maint.open()

        rx = maint.command(b"00FFAB", "AB")
        mode = parse_ab_mode(rx)
        if mode is not None:
            print(f"Initial HMI mode: {mode:02X}")

        if not args.skip_system_transition and mode != 0x07:
            enter_system_transmission(args.host, maint, args.debug)

        print("Preparing HMI for OS download...")
        maint.command(b"00FFLE", "LE", timeout=200)

        print("Opening temporary FTP session...")
        maint.command(make_lb_body(username, password), "LB")

        ftp = wait_for_ftp(args.host, username, password, args.debug)

        maint.start_lf()
        try:
            upload_znx(ftp, path, md5_hex)
        finally:
            maint.stop_lf()

        try:
            ftp.quit()
        except all_errors:
            try:
                ftp.close()
            except Exception:
                pass
        ftp = None

        print("Starting kernel install. This may take a long time...")
        # LinuxDownloadMode.Kernel == 1, encoded as a little-endian Int16.
        maint.command(b"00FFLC" + struct.pack("<h", 1), "LC Kernel",
                      timeout=1900)
        lc_ok = True

        maint.command(b"00FFLD", "LD", timeout=30)

        try:
            maint.command(b"00FFAH", "AH", timeout=30)
        except Exception as exc:
            print(f"AH warning: {exc}")

        print("ZNX download sequence completed.")

    except KeyboardInterrupt:
        print("\nInterrupted.")
        raise SystemExit(130)

    finally:
        maint.stop_lf()

        if ftp is not None:
            try:
                ftp.close()
            except Exception:
                pass

        if maint.sock is not None and not lc_ok:
            try:
                maint.command(b"00FFLD", "LD cleanup", timeout=10)
            except Exception:
                pass

        maint.close()


if __name__ == "__main__":
    main()
