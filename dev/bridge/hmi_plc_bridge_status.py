#!/usr/bin/env python3
"""Poll IDEC PLCs and serve the selected PLC to an IDEC HMI.

The process has two roles:

1. Maintenance-protocol client: reads the configured register map from every PLC.
2. Maintenance-protocol server: answers the HMI on TCP port 2101 from a cache.

D10399 is used as the HMI unit selector. Unit 1 selects the first PLC, unit 2
selects the second, and so on. Other HMI writes are blocked unless
--enable-writes is supplied.

Each PLC config may optionally define::

    "plc_run_register": "M8000",
    "unit_run_register": "M0000",

M8000 defaults to the PLC program-running status. The unit-run register is
application-specific and is not assumed unless configured.

Register entries may contain either three fields (name, address, datatype) or
an older fourth logger/plotter flag. HMI writes are retargeted to the selected
PLC's configured device number before forwarding.
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


class PlcCommunicationError(IOError):
    """The PLC did not complete a maintenance-protocol exchange."""


class PlcPollError(IOError):
    """The PLC replied, but a configured poll could not be decoded."""


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
        raise PlcPollError(f"invalid reply: {reply!r}")
    if reply[3:4] == b"2":
        code = reply[4:6].decode("ascii", "replace")
        raise PlcPollError(f"PLC NG {code}")
    if reply[3:4] != b"0":
        raise PlcPollError(
            f"unexpected PLC reply command: {reply[3:4]!r}"
        )
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


def register_entries(entries, source: str):
    """Yield name, address, datatype from 3- or 4-field map entries.

    Older MiSm maps may include a fourth logger/plotter flag. It is metadata
    for the logger and is not a read/write permission flag for this bridge.
    """
    for index, entry in enumerate(entries):
        if not isinstance(entry, (tuple, list)) or len(entry) < 3:
            raise ValueError(
                f"{source}[{index}] must contain name, address, datatype"
            )
        name, address, datatype = entry[:3]
        yield str(name), str(address), str(datatype)


def m_address_to_index(address: int) -> int:
    """Convert an IDEC M address to a linear bit index.

    The rightmost M-address digit is octal. For example, the address after
    M0007 is M0010, not M0008.
    """
    bit = address % 10
    if bit > 7:
        raise ValueError(f"invalid M address: M{address:04d}")
    return (address // 10) * 8 + bit


def m_index_to_address(index: int) -> int:
    """Convert a linear bit index back to IDEC M-address notation."""
    if index < 0:
        raise ValueError(f"invalid M bit index: {index}")
    return (index // 8) * 10 + (index % 8)


def m_address_offset(address: int, offset: int) -> int:
    return m_index_to_address(m_address_to_index(address) + offset)


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
    plc_run_address: int | None = 8000
    unit_run_address: int | None = None
    online: bool = False
    last_ok: float = 0.0
    last_error: str = ""
    poll_error: str = ""
    reported_bits: dict[str, int] = field(default_factory=dict)
    lock: threading.RLock = field(default_factory=threading.RLock)

    def set_status(self, online: bool, error: str = "") -> bool:
        with self.lock:
            changed = self.online != online
            self.online = online
            self.last_error = error
            if online:
                self.last_ok = time.monotonic()
        return changed

    def set_poll_error(self, error: str) -> bool:
        with self.lock:
            changed = self.poll_error != error
            self.poll_error = error
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
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                if self.sock is None:
                    self.connect()
                assert self.sock is not None
                self.sock.sendall(request)
                reply = recv_frame(self.sock)
                if not reply:
                    raise OSError("empty PLC reply")
                return reply
            except OSError as exc:
                last_error = exc
                self.close()
                if attempt:
                    break
        raise PlcCommunicationError(str(last_error or "request failed"))

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class Bridge:
    def __init__(self, plcs: list[PlcState], plan: RegisterPlan,
                 bind_ip: str, advertise_ip: str, port: int,
                 timeout: float, poll_interval: float,
                 allow_writes: bool, passthrough: bool,
                 write_names: dict[tuple[str, int], str] | None = None):
        self.plcs = plcs
        self.plan = plan
        self.bind_ip = bind_ip
        self.advertise_ip = advertise_ip
        self.port = port
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.allow_writes = allow_writes
        self.passthrough = passthrough
        self.write_names = write_names or {}
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
        # M relays are application data. Do not replace program-specific
        # registers such as M0950/M0951 with bridge-generated values.
        return None

    @staticmethod
    def unpack_m_bits(data: bytes, start: int, bit_count: int) -> dict[int, int]:
        expected_chars = ((bit_count + 7) // 8) * 2
        if len(data) != expected_chars:
            raise PlcPollError(
                f"M{start:04d} returned {len(data)} ASCII characters; "
                f"expected {expected_chars}"
            )
        try:
            packed = bytes.fromhex(data.decode("ascii"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise PlcPollError(f"M{start:04d} returned invalid hex data") from exc

        values: dict[int, int] = {}
        for offset in range(bit_count):
            byte = packed[offset // 8]
            address = m_address_offset(start, offset)
            values[address] = (byte >> (offset % 8)) & 1
        return values

    @staticmethod
    def pack_m_bits(values: list[int]) -> bytes:
        packed = bytearray((len(values) + 7) // 8)
        for offset, value in enumerate(values):
            if value:
                packed[offset // 8] |= 1 << (offset % 8)
        return packed.hex().upper().encode("ascii")

    def report_run_status(self, plc: PlcState):
        checks = [
            ("plc_run", plc.plc_run_address, "PLC program stopped",
             "PLC program running"),
            ("unit_run", plc.unit_run_address, "Unit not running",
             "Unit running"),
        ]
        with plc.lock:
            for key, address, off_text, on_text in checks:
                if address is None or address not in plc.bits:
                    continue
                value = plc.bits[address]
                if plc.reported_bits.get(key) == value:
                    continue
                plc.reported_bits[key] = value
                message = on_text if value else off_text
                print(f"{message}: unit {plc.number} {plc.ip}, "
                      f"M{address:04d} = {value}")

    def mark_online(self, plc: PlcState):
        if plc.set_status(True):
            print(f"PLC online: unit {plc.number} {plc.ip}")

    def mark_offline(self, plc: PlcState, error: str):
        if plc.set_status(False, error):
            print(f"PLC offline: unit {plc.number} {plc.ip}: {error}")

    def poll_plc(self, plc: PlcState):
        with MaintSession(plc.ip, self.port, self.timeout) as session:
            words: dict[int, int] = {}
            bits: dict[int, int] = {}
            timers: dict[int, int] = {}

            for start, count in self.plan.d_ranges:
                nbytes = count * 2
                payload = f"{start:04d}{nbytes:02X}".encode("ascii")
                try:
                    data = reply_data(session.request(
                        frame_request(plc.device, "R", "D", payload)
                    ))
                except PlcPollError as exc:
                    raise PlcPollError(
                        f"RD D{start:04d}, {nbytes} bytes: {exc}"
                    ) from exc
                if len(data) != count * 4:
                    raise PlcPollError(
                        f"RD D{start:04d} returned {len(data)} ASCII characters; "
                        f"expected {count * 4}"
                    )
                for offset in range(count):
                    pos = offset * 4
                    words[start + offset] = int(data[pos:pos + 4], 16)

            for start, bit_count in self.plan.m_ranges:
                nbytes = (bit_count + 7) // 8
                payload = f"{start:04d}{nbytes:02X}".encode("ascii")
                try:
                    data = reply_data(session.request(
                        frame_request(plc.device, "R", "M", payload)
                    ))
                except PlcPollError as exc:
                    end = m_address_offset(start, bit_count - 1)
                    raise PlcPollError(
                        f"RM M{start:04d}-M{end:04d}, {nbytes} bytes: {exc}"
                    ) from exc
                bits.update(self.unpack_m_bits(data, start, bit_count))

            for timer in self.plan.timers:
                payload = f"{timer:04d}02".encode("ascii")
                try:
                    data = reply_data(session.request(
                        frame_request(plc.device, "R", "t", payload)
                    ))
                except PlcPollError as exc:
                    raise PlcPollError(
                        f"Rt T{timer:04d}, 2 bytes: {exc}"
                    ) from exc
                if len(data) != 4:
                    raise PlcPollError(
                        f"Rt T{timer:04d} returned {len(data)} ASCII characters; "
                        "expected 4"
                    )
                timers[timer] = int(data, 16)

        with plc.lock:
            plc.words.update(words)
            plc.bits.update(bits)
            plc.timer_words.update(timers)
        self.mark_online(plc)
        if plc.set_poll_error(""):
            print(f"PLC poll recovered: unit {plc.number} {plc.ip}")
        self.report_run_status(plc)

    def poll_loop(self, plc: PlcState):
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.poll_plc(plc)
            except PlcCommunicationError as exc:
                self.mark_offline(plc, str(exc))
            except PlcPollError as exc:
                # A valid reply or PLC NG response means the PLC is reachable.
                # This is a register-map/polling problem, not an offline PLC.
                self.mark_online(plc)
                if plc.set_poll_error(str(exc)):
                    print(f"PLC poll error: unit {plc.number} {plc.ip}: {exc}")
            except Exception as exc:
                self.mark_online(plc)
                if plc.set_poll_error(str(exc)):
                    print(f"PLC poll error: unit {plc.number} {plc.ip}: {exc}")
            delay = self.poll_interval - (time.monotonic() - started)
            self.stop_event.wait(max(0.05, delay))

    @staticmethod
    def rewrite_request_device(frame: bytes, device: str) -> bytes:
        """Retarget an HMI request to the configured PLC device number."""
        encoded = device.encode("ascii")
        if len(encoded) != 2:
            raise ValueError(f"invalid PLC device number: {device!r}")
        body = bytearray(frame[:-3])
        body[1:3] = encoded
        rebuilt = bytes(body)
        return rebuilt + bcc(rebuilt) + b"\r"

    def proxy(self, frame: bytes) -> bytes:
        plc = self.selected_plc()
        if plc is None:
            return frame_ng("06")
        try:
            outbound = self.rewrite_request_device(frame, plc.device)
            with socket.create_connection((plc.ip, self.port),
                                          timeout=self.timeout) as sock:
                sock.settimeout(self.timeout)
                sock.sendall(outbound)
                reply = recv_frame(sock)
                if not reply:
                    raise OSError("empty PLC reply")
                self.mark_online(plc)
                return reply
        except (OSError, ValueError) as exc:
            self.mark_offline(plc, str(exc))
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
            try:
                addresses = [m_address_offset(address, offset)
                             for offset in range(count)]
            except ValueError:
                return None
            with plc.lock:
                for addr in addresses:
                    synthetic = self.synthetic_bit(addr)
                    if synthetic is not None:
                        values.append(synthetic)
                    elif addr in plc.bits:
                        values.append(plc.bits[addr])
                    else:
                        return None
            return self.pack_m_bits(values)

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
        elif dtype in {"M", "X", "Y", "R"}:
            count = nbytes * 8
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

        if dtype in {"D", "A", "t"}:
            fill = b"0" * (count * 4)
        elif dtype in {"M", "X", "Y", "R"}:
            fill = b"00" * nbytes
        else:
            fill = b"0" * count
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

    @staticmethod
    def write_reply_error(reply: bytes) -> str | None:
        if not validate_frame(reply) or reply[:1] != b"\x06":
            return f"invalid reply {reply!r}"
        if reply[3:4] == b"0":
            return None
        if reply[3:4] == b"2":
            return f"PLC NG {reply[4:6].decode('ascii', 'replace')}"
        return f"unexpected reply command {reply[3:4]!r}"

    def write_label(self, dtype: str, address: int) -> str:
        key = (dtype.upper(), address)
        name = self.write_names.get(key)
        if name:
            return f"{name} "
        return ""

    def apply_successful_write(self, dtype: str, payload: bytes):
        plc = self.selected_plc()
        if plc is None:
            return

        try:
            if dtype == "m":
                if len(payload) != 5 or payload[4:5] not in {b"0", b"1"}:
                    raise ValueError("invalid Wm payload")
                address = int(payload[:4], 10)
                m_address_to_index(address)
                value = int(payload[4:5])
                with plc.lock:
                    plc.bits[address] = value
                label = self.write_label("M", address)
                print(f"HMI write: unit {plc.number} {plc.ip}, "
                      f"{label}M{address:04d} = {value}")
                return

            if dtype == "M":
                if len(payload) < 6:
                    raise ValueError("short WM payload")
                address = int(payload[:4], 10)
                nbytes = int(payload[4:6], 16)
                data = payload[6:]
                if len(data) != nbytes * 2:
                    raise ValueError("WM data length mismatch")
                values = self.unpack_m_bits(data, address, nbytes * 8)
                with plc.lock:
                    plc.bits.update(values)
                end = m_address_offset(address, nbytes * 8 - 1)
                print(f"HMI write: unit {plc.number} {plc.ip}, "
                      f"M{address:04d}-M{end:04d} = "
                      f"{data.decode('ascii', 'replace')}")
                return

            if dtype == "D":
                if len(payload) < 6:
                    raise ValueError("short WD payload")
                address = int(payload[:4], 10)
                nbytes = int(payload[4:6], 16)
                data = payload[6:]
                if nbytes % 2 or len(data) != nbytes * 2:
                    raise ValueError("WD data length mismatch")
                values = [int(data[pos:pos + 4], 16)
                          for pos in range(0, len(data), 4)]
                with plc.lock:
                    for offset, value in enumerate(values):
                        plc.words[address + offset] = value
                end = address + len(values) - 1
                target = (f"D{address:04d}" if end == address else
                          f"D{address:04d}-D{end:04d}")
                #
                if len(values) == 1:
                    label = self.write_label("D", address)
                    print(
                        f"HMI write: unit {plc.number} {plc.ip}, "
                        f"{label}D{address:04d} = {values[0]}"
                    )
                else:
                    formatted = ", ".join(str(value) for value in values)
                    print(
                        f"HMI write: unit {plc.number} {plc.ip}, "
                        f"{target} = [{formatted}]"
                    )
                return
                
        except (ValueError, UnicodeDecodeError) as exc:
            print(f"HMI write cache update skipped: unit {plc.number} "
                  f"{plc.ip}: W{dtype} payload {payload!r}: {exc}")

    def handle_write(self, frame: bytes, dtype: str, payload: bytes) -> bytes:
        selected = self.intercept_unit_write(dtype, payload)
        if selected is not None:
            return selected
        if not self.allow_writes:
            return frame_ng("02")

        reply = self.proxy(frame)
        error = self.write_reply_error(reply)
        if error is None:
            self.apply_successful_write(dtype, payload)
        else:
            plc = self.selected_plc()
            target = f"unit {plc.number} {plc.ip}" if plc else "no unit"
            print(f"HMI write failed: {target}, W{dtype} "
                  f"payload {payload!r}: {error}")
        return reply

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

    def add_register(address: str, datatype: str):
        dtype, number = split_register(address)
        if dtype == "D":
            d_words.add(number)
            if datatype.upper() == "F":
                d_words.add(number + 1)
        elif dtype == "M":
            m_address_to_index(number)
            m_bits.add(number)

    for _, address, datatype in register_entries(
            configs[0].get("registers", []), "PLC_CONFIGS[0].registers"):
        add_register(address, datatype)

    for _, address, datatype in register_entries(
            getattr(module, "HMI_WRITE_COMMANDS", []),
            "HMI_WRITE_COMMANDS"):
        add_register(address, datatype)

    for config in configs:
        plc_run = config.get("plc_run_register", "M8000")
        unit_run = config.get("unit_run_register")
        for address in (plc_run, unit_run):
            if not address:
                continue
            dtype, number = split_register(str(address))
            if dtype != "M":
                raise ValueError(f"run status register must be M: {address}")
            m_address_to_index(number)
            m_bits.add(number)

    for _, address, datatype in register_entries(
            getattr(module, "OPTIONAL_META_REGISTERS", []),
            "OPTIONAL_META_REGISTERS"):
        add_register(address, datatype)

    # RM data length is bytes. M addresses are not ordinary decimal numbers:
    # the rightmost digit is octal, so M0007 is followed by M0010. Convert to
    # linear bit indexes before aligning each poll to a 16-bit block.
    m_block_indexes = {
        (m_address_to_index(number) // 16) * 16 for number in m_bits
    }
    m_block_starts = sorted(m_index_to_address(index)
                            for index in m_block_indexes)
    m_ranges = [(start, 16) for start in m_block_starts]
    timers = sorted(number for _, number in
                    getattr(module, "HMI_TIMER_CURRENT_VALUES", []))
    return RegisterPlan(
        d_ranges=merge_ranges(d_words, max_gap=3, max_count=64),
        m_ranges=m_ranges,
        timers=timers,
    )


def build_write_names(module) -> dict[tuple[str, int], str]:
    names: dict[tuple[str, int], str] = {}
    for name, address, _ in register_entries(
            getattr(module, "HMI_WRITE_COMMANDS", []),
            "HMI_WRITE_COMMANDS"):
        dtype, number = split_register(address)
        names[(dtype, number)] = name
    return names


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
        plc_run = config.get("plc_run_register", "M8000")
        unit_run = config.get("unit_run_register")
        plc_run_address = (
            split_register(str(plc_run))[1] if plc_run else None
        )
        unit_run_address = (
            split_register(str(unit_run))[1] if unit_run else None
        )
        plcs.append(PlcState(
            number=number,
            name=config.get("name", f"p{number}"),
            ip=ip,
            device=str(config.get("device", "FF")),
            endian=int(config.get("endian", 0)),
            plc_run_address=plc_run_address,
            unit_run_address=unit_run_address,
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
        write_names=build_write_names(module),
    )
    bridge.serve()


if __name__ == "__main__":
    main()
