#!/usr/bin/env python3
"""Poll IDEC PLCs and serve the selected PLC to an IDEC HMI.

The process has two roles:

1. Maintenance-protocol client: reads the configured register map from every PLC.
2. Maintenance-protocol server: answers the HMI on TCP port 2101 from a cache.

D10399 is used as the HMI unit selector. Unit 1 selects the first PLC, unit 2
selects the second, and so on. Other HMI writes are blocked unless
--enable-writes is supplied.
"""

from __future__ import annotations

import argparse
import importlib.util
import ipaddress
import re
import socket
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

DEFAULT_PORT = 2101
DEFAULT_TIMEOUT = 1.0
DEFAULT_EXCLUDE = {"192.168.1.20", "192.168.1.61", "192.168.1.150"}


def bcc(data: bytes, include_control: bool = True) -> bytes:
    value = 0
    start = 0 if include_control else 1
    for byte in data[start:]:
        value ^= byte
    return f"{value:02X}".encode("ascii")


def frame_request(device: str, command: str, dtype: str, payload: bytes) -> bytes:
    body = b"\x05" + device.encode("ascii") + b"0"
    body += command.encode("ascii") + dtype.encode("ascii") + payload
    return body + bcc(body) + b"\r"


def frame_ack(data: bytes = b"", device: str = "00") -> bytes:
    body = b"\x06" + device.encode("ascii") + b"0" + data
    return body + bcc(body) + b"\r"


def frame_ng(code: str = "06", device: str = "00") -> bytes:
    body = b"\x06" + device.encode("ascii") + b"2" + code.encode("ascii")
    return body + bcc(body) + b"\r"


def validate_frame(frame: bytes) -> bool:
    if len(frame) < 7 or frame[-1:] != b"\r":
        return False
    body = frame[:-3]
    sent = frame[-3:-1].upper()
    return sent in {bcc(body, True), bcc(body, False)}


def recv_frame(sock: socket.socket, limit: int = 65536) -> bytes:
    data = bytearray()
    while len(data) < limit:
        chunk = sock.recv(4096)
        if not chunk:
            break
        data.extend(chunk)
        pos = data.find(b"\r")
        if pos >= 0:
            return bytes(data[:pos + 1])
    return bytes(data)


def reply_data(reply: bytes) -> bytes:
    if not validate_frame(reply) or reply[:1] != b"\x06":
        raise IOError(f"invalid reply: {reply!r}")
    if reply[3:4] == b"2":
        raise IOError(f"PLC NG {reply[4:6].decode('ascii', 'replace')}")
    if reply[3:4] != b"0":
        raise IOError(f"unexpected PLC reply command: {reply[3:4]!r}")
    return reply[4:-3]


def parse_ip(value: str) -> tuple[int, int, int, int]:
    ip = ipaddress.ip_address(value)
    if ip.version != 4:
        raise ValueError("only IPv4 is supported")
    return tuple(int(part) for part in str(ip).split("."))


def load_map(path: Path):
    spec = importlib.util.spec_from_file_location("hmi_register_map", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load register map: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_register(address: str) -> tuple[str, int]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", address.strip())
    if not match:
        raise ValueError(f"unsupported register address: {address}")
    return match.group(1).upper(), int(match.group(2))


def merge_ranges(values: Iterable[int], max_gap: int = 0,
                 max_count: int = 64) -> list[tuple[int, int]]:
    numbers = sorted(set(values))
    if not numbers:
        return []

    ranges: list[tuple[int, int]] = []
    start = end = numbers[0]
    for number in numbers[1:]:
        proposed_count = number - start + 1
        if number <= end + max_gap + 1 and proposed_count <= max_count:
            end = number
            continue
        ranges.append((start, end - start + 1))
        start = end = number
    ranges.append((start, end - start + 1))
    return ranges


def is_open(ip: str, port: int, timeout: float = 0.15) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def discover_plcs(interface: str, port: int, exclude: set[str]) -> list[str]:
    command = ["arp-scan", "-I", interface, "-l"]
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                check=False, timeout=20)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        print(f"PLC discovery unavailable: {exc}")
        return []

    found = []
    pattern = re.compile(
        r"^(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})\b",
        re.MULTILINE,
    )
    for ip, mac in pattern.findall(result.stdout):
        if ip in exclude or not mac.lower().startswith("00:03:7b:"):
            continue
        if is_open(ip, port):
            found.append(ip)
    return sorted(set(found), key=ipaddress.ip_address)


@dataclass
class RegisterPlan:
    d_ranges: list[tuple[int, int]]
    m_ranges: list[tuple[int, int]]
    timers: list[int]


@dataclass
class PlcState:
    number: int
    name: str
    ip: str
    device: str = "FF"
    endian: int = 0
    words: dict[int, int] = field(default_factory=dict)
    bits: dict[int, int] = field(default_factory=dict)
    timer_words: dict[int, int] = field(default_factory=dict)
    online: bool = False
    last_ok: float = 0.0
    last_error: str = ""
    lock: threading.RLock = field(default_factory=threading.RLock)

    def set_status(self, online: bool, error: str = "") -> bool:
        with self.lock:
            changed = self.online != online
            self.online = online
            self.last_error = error
            if online:
                self.last_ok = time.monotonic()
        return changed


class MaintSession:
    def __init__(self, ip: str, port: int, timeout: float):
        self.ip = ip
        self.port = port
        self.timeout = timeout
        self.sock: socket.socket | None = None

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def connect(self):
        self.close()
        self.sock = socket.create_connection((self.ip, self.port),
                                             timeout=self.timeout)
        self.sock.settimeout(self.timeout)

    def request(self, request: bytes) -> bytes:
        for attempt in range(2):
            try:
                if self.sock is None:
                    self.connect()
                assert self.sock is not None
                self.sock.sendall(request)
                reply = recv_frame(self.sock)
                if not reply:
                    raise IOError("empty PLC reply")
                return reply
            except (OSError, IOError):
                self.close()
                if attempt:
                    raise
        raise IOError("request failed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class Bridge:
    def __init__(self, plcs: list[PlcState], plan: RegisterPlan,
                 bind_ip: str, advertise_ip: str, port: int,
                 timeout: float, poll_interval: float,
                 allow_writes: bool, passthrough: bool):
        self.plcs = plcs
        self.plan = plan
        self.bind_ip = bind_ip
        self.advertise_ip = advertise_ip
        self.port = port
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.allow_writes = allow_writes
        self.passthrough = passthrough
        self.selected = 1
        self.stop_event = threading.Event()
        self.select_lock = threading.RLock()

    def selected_plc(self) -> PlcState | None:
        with self.select_lock:
            if not self.plcs or self.selected < 1 or self.selected > len(self.plcs):
                return None
            return self.plcs[self.selected - 1]

    def select_unit(self, number: int) -> bool:
        if number < 1 or number > len(self.plcs):
            return False
        with self.select_lock:
            changed = self.selected != number
            self.selected = number
        if changed:
            plc = self.selected_plc()
            print(f"HMI selected unit {number}: {plc.ip if plc else 'none'}")
        return True

    def synthetic_word(self, address: int) -> int | None:
        plc = self.selected_plc()
        if address == 10399:
            return self.selected
        if 10400 <= address <= 10403:
            return parse_ip(self.advertise_ip)[address - 10400]
        if address == 10392:
            return 0 if plc and plc.online else 1
        if address == 10500:
            return 0
        return None

    def synthetic_bit(self, address: int) -> int | None:
        plc = self.selected_plc()
        if address in {950, 951}:
            return int(bool(plc and plc.online))
        return None

    def poll_plc(self, plc: PlcState):
        with MaintSession(plc.ip, self.port, self.timeout) as session:
            words: dict[int, int] = {}
            bits: dict[int, int] = {}
            timers: dict[int, int] = {}

            for start, count in self.plan.d_ranges:
                payload = f"{start:04d}{count * 2:02X}".encode("ascii")
                data = reply_data(session.request(
                    frame_request(plc.device, "R", "D", payload)
                ))
                if len(data) != count * 4:
                    raise IOError(f"D{start:04d} returned {len(data)} bytes ASCII")
                for offset in range(count):
                    pos = offset * 4
                    words[start + offset] = int(data[pos:pos + 4], 16)

            for start, count in self.plan.m_ranges:
                payload = f"{start:04d}{count:02X}".encode("ascii")
                data = reply_data(session.request(
                    frame_request(plc.device, "R", "M", payload)
                ))
                if len(data) != count:
                    raise IOError(f"M{start:04d} returned {len(data)} bits")
                for offset, value in enumerate(data):
                    bits[start + offset] = 1 if value == ord("1") else 0

            for timer in self.plan.timers:
                payload = f"{timer:04d}02".encode("ascii")
                data = reply_data(session.request(
                    frame_request(plc.device, "R", "t", payload)
                ))
                if len(data) == 4:
                    timers[timer] = int(data, 16)

        with plc.lock:
            plc.words.update(words)
            plc.bits.update(bits)
            plc.timer_words.update(timers)
        if plc.set_status(True):
            print(f"PLC online: unit {plc.number} {plc.ip}")

    def poll_loop(self, plc: PlcState):
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.poll_plc(plc)
            except Exception as exc:
                if plc.set_status(False, str(exc)):
                    print(f"PLC offline: unit {plc.number} {plc.ip}: {exc}")
            delay = self.poll_interval - (time.monotonic() - started)
            self.stop_event.wait(max(0.05, delay))

    def proxy(self, frame: bytes) -> bytes:
        plc = self.selected_plc()
        if plc is None:
            return frame_ng("06")
        try:
            with socket.create_connection((plc.ip, self.port),
                                          timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                sock.sendall(frame)
                reply = recv_frame(sock)
                if not reply:
                    raise IOError("empty PLC reply")
                plc.set_status(True)
                return reply
        except Exception as exc:
            plc.set_status(False, str(exc))
            return frame_ng("06")

    def read_cached(self, dtype: str, address: int, count: int) -> bytes | None:
        plc = self.selected_plc()
        if plc is None:
            return None

        if dtype == "D":
            values = []
            with plc.lock:
                for addr in range(address, address + count):
                    synthetic = self.synthetic_word(addr)
                    if synthetic is not None:
                        values.append(synthetic)
                    elif addr in plc.words:
                        values.append(plc.words[addr])
                    else:
                        return None
            return "".join(f"{value & 0xFFFF:04X}" for value in values).encode()

        if dtype == "M":
            values = []
            with plc.lock:
                for addr in range(address, address + count):
                    synthetic = self.synthetic_bit(addr)
                    if synthetic is not None:
                        values.append(synthetic)
                    elif addr in plc.bits:
                        values.append(plc.bits[addr])
                    else:
                        return None
            return "".join("1" if value else "0" for value in values).encode()

        if dtype == "t":
            values = []
            with plc.lock:
                for addr in range(address, address + count):
                    if addr not in plc.timer_words:
                        return None
                    values.append(plc.timer_words[addr])
            return "".join(f"{value & 0xFFFF:04X}" for value in values).encode()

        return None

    def read_extended_words(self, address: int, count: int) -> bytes | None:
        values = []
        for addr in range(address, address + count):
            value = self.synthetic_word(addr)
            if value is None:
                return None
            values.append(value)
        return "".join(f"{value & 0xFFFF:04X}" for value in values).encode()

    def handle_read(self, frame: bytes, dtype: str, payload: bytes) -> bytes:
        if len(payload) < 6:
            return frame_ng("06")

        try:
            address = int(payload[:4], 16 if dtype in {"A", "l"} else 10)
            nbytes = int(payload[4:6], 16)
        except ValueError:
            return frame_ng("06")

        if dtype in {"D", "A", "t"}:
            if nbytes % 2:
                return frame_ng("06")
            count = nbytes // 2
        else:
            count = nbytes

        data = None
        if dtype in {"D", "M", "t"}:
            data = self.read_cached(dtype, address, count)
        elif dtype == "A":
            data = self.read_extended_words(address, count)

        if data is not None:
            return frame_ack(data)
        if self.passthrough:
            return self.proxy(frame)

        fill = b"0" * (count * 4 if dtype in {"D", "A", "t"} else count)
        return frame_ack(fill)

    def intercept_unit_write(self, dtype: str, payload: bytes) -> bytes | None:
        if dtype != "A" or len(payload) < 10:
            return None
        try:
            address = int(payload[:4], 16)
            nbytes = int(payload[4:6], 16)
            value = int(payload[6:10], 16)
        except ValueError:
            return frame_ng("06")
        if address != 10399 or nbytes != 2:
            return None
        return frame_ack() if self.select_unit(value) else frame_ng("06")

    def handle_write(self, frame: bytes, dtype: str, payload: bytes) -> bytes:
        selected = self.intercept_unit_write(dtype, payload)
        if selected is not None:
            return selected
        if not self.allow_writes:
            return frame_ng("02")
        return self.proxy(frame)

    def handle_frame(self, frame: bytes) -> bytes:
        if not validate_frame(frame) or frame[:1] != b"\x05" or len(frame) < 9:
            return frame_ng("10")

        command = frame[4:5].decode("ascii", "replace")
        dtype = frame[5:6].decode("ascii", "replace")
        payload = frame[6:-3]

        if command == "R":
            return self.handle_read(frame, dtype, payload)
        if command == "W":
            return self.handle_write(frame, dtype, payload)
        if self.passthrough:
            return self.proxy(frame)
        return frame_ng("06")

    def client_loop(self, client: socket.socket, peer):
        client.settimeout(10.0)
        buffer = bytearray()
        try:
            while not self.stop_event.is_set():
                chunk = client.recv(4096)
                if not chunk:
                    return
                buffer.extend(chunk)
                while True:
                    pos = buffer.find(b"\r")
                    if pos < 0:
                        break
                    request = bytes(buffer[:pos + 1])
                    del buffer[:pos + 1]
                    client.sendall(self.handle_frame(request))
        except (ConnectionError, OSError, socket.timeout):
            return
        finally:
            client.close()

    def serve(self):
        for plc in self.plcs:
            thread = threading.Thread(target=self.poll_loop, args=(plc,),
                                      daemon=True)
            thread.start()

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.bind_ip, self.port))
            server.listen(16)
            server.settimeout(1.0)
            print(f"Serving HMI on {self.bind_ip}:{self.port}")
            print(f"Advertised master IP: {self.advertise_ip}")
            print(f"PLC writes: {'enabled' if self.allow_writes else 'blocked'}")
            print(f"Uncached requests: {'proxied' if self.passthrough else 'zero-filled'}")
            print("Unit map:")
            for plc in self.plcs:
                print(f"  {plc.number}: {plc.name} {plc.ip}")

            try:
                while not self.stop_event.is_set():
                    try:
                        client, peer = server.accept()
                    except socket.timeout:
                        continue
                    thread = threading.Thread(target=self.client_loop,
                                              args=(client, peer), daemon=True)
                    thread.start()
            except KeyboardInterrupt:
                print("Stopping")
            finally:
                self.stop_event.set()


def build_plan(module) -> RegisterPlan:
    configs = list(getattr(module, "PLC_CONFIGS", []))
    if not configs:
        raise ValueError("register map has no PLC_CONFIGS")

    d_words: set[int] = set()
    m_bits: set[int] = set()
    for _, address, datatype, _ in configs[0]["registers"]:
        dtype, number = split_register(address)
        if dtype == "D":
            d_words.add(number)
            if datatype.upper() == "F":
                d_words.add(number + 1)
        elif dtype == "M":
            m_bits.add(number)

    for _, address, datatype in getattr(module, "OPTIONAL_META_REGISTERS", []):
        dtype, number = split_register(address)
        if dtype == "D":
            d_words.add(number)
            if datatype.upper() == "F":
                d_words.add(number + 1)

    # Read complete 16-bit M blocks. This matches the HMI's normal RM pattern.
    m_block_starts = sorted({(number // 16) * 16 for number in m_bits})
    m_ranges = [(start, 16) for start in m_block_starts]
    timers = sorted(number for _, number in
                    getattr(module, "HMI_TIMER_CURRENT_VALUES", []))
    return RegisterPlan(
        d_ranges=merge_ranges(d_words, max_gap=3, max_count=64),
        m_ranges=m_ranges,
        timers=timers,
    )


def make_plcs(module, explicit: list[str], discovered: list[str]) -> list[PlcState]:
    configs = list(getattr(module, "PLC_CONFIGS", []))
    by_ip = {config["ip"]: config for config in configs}

    if explicit:
        candidates = list(explicit)
    elif discovered:
        candidates = list(discovered)
    else:
        candidates = [config["ip"] for config in configs]

    ips = []
    for ip in candidates:
        if ip not in ips:
            ips.append(ip)

    plcs = []
    for number, ip in enumerate(ips, 1):
        config = by_ip.get(ip, {})
        plcs.append(PlcState(
            number=number,
            name=config.get("name", f"p{number}"),
            ip=ip,
            device=str(config.get("device", "FF")),
            endian=int(config.get("endian", 0)),
        ))
    return plcs


def parse_args():
    parser = argparse.ArgumentParser(
        description="Cache PLC registers and serve them to an IDEC HMI"
    )
    parser.add_argument("--map", type=Path, default=Path("R513a_Register_map.py"))
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--advertise-ip", default="192.168.1.160")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT)
    parser.add_argument("--poll", type=float, default=0.5,
                        help="seconds between PLC cache refreshes")
    parser.add_argument("--plc", action="append", default=[],
                        help="PLC IP; repeat for multiple PLCs")
    parser.add_argument("--discover", action="store_true",
                        help="find IDEC devices with arp-scan and verify port 2101")
    parser.add_argument("--interface", default="enp2s0")
    parser.add_argument("--exclude", action="append", default=[])
    parser.add_argument("--enable-writes", action="store_true",
                        help="forward HMI writes to the selected PLC")
    parser.add_argument("--no-passthrough", action="store_true",
                        help="zero-fill uncached reads instead of proxying them")
    return parser.parse_args()


def main():
    args = parse_args()
    module = load_map(args.map)
    plan = build_plan(module)

    exclude = DEFAULT_EXCLUDE | set(args.exclude) | {args.advertise_ip}
    discovered = []
    if args.discover:
        discovered = discover_plcs(args.interface, args.port, exclude)
        print("Discovered PLCs:", ", ".join(discovered) if discovered else "none")

    plcs = make_plcs(module, args.plc, discovered)
    if not plcs:
        raise SystemExit("No PLCs configured or discovered")

    bridge = Bridge(
        plcs=plcs,
        plan=plan,
        bind_ip=args.bind,
        advertise_ip=args.advertise_ip,
        port=args.port,
        timeout=args.timeout,
        poll_interval=max(0.1, args.poll),
        allow_writes=args.enable_writes,
        passthrough=not args.no_passthrough,
    )
    bridge.serve()


if __name__ == "__main__":
    main()
