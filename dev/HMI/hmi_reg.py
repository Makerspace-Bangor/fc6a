#!/usr/bin/env python3
"""
Live IDEC HMI maintenance-protocol request monitor.

The HMI connects to this program as though it were its configured PLC. Read
requests receive zero-filled replies. Write requests are acknowledged but are
not forwarded to a real PLC.

Normal mode records each unique request once, matching hmi_register_logger2.py.
Live mode watches the active READ request set and reports only changes:

    python3 hmi_reg.py --live

Live mode intentionally compares request commands, addresses, and counts. It
never compares the values returned in read replies. Repeated WRITE requests are
shown as events because a button press may write the same register more than
once without changing screens.

python3 hmi_reg.py --live \
    --live-warmup 2.0 \
    --live-hold 2.0 \
    --live-debounce 0.15

"""

import argparse
import csv
import os
import socket
import sys
import time
from collections import OrderedDict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

HOST = "0.0.0.0"
PORT = 2101
DEFAULT_CSV = "hmi_registers.txt"

COMMAND_DESCRIPTIONS = {
    "RD": "Read D data registers (16-bit words).",
    "RM": "Read M internal relay bits.",
    "RA": "Read extended D-register area using a hexadecimal address.",
    "R_": "Read timer register.",
    "WA": "Write extended D-register area using a hexadecimal address.",
    "WD": "Write D data register(s).",
    "WM": "Write M internal relay byte block.",
    "Wm": "Write one M internal relay bit.",
    "Rl": "Observed lowercase-l read; exact operand meaning is not documented.",
}

# Preserve the nonzero value used by the original emulator.
D_VALUES = {
    570: 26,
}

CSV_FIELDS = [
    "access",
    "command",
    "operand",
    "register_range",
    "start_address",
    "end_address",
    "item_count",
    "item_unit",
    "request_bytes",
    "first_seen",
    "last_seen",
    "request_count",
    "valid_bcc",
    "payload",
    "raw_request",
    "raw_hex",
]


def command_help_text():
    width = max(len(command) for command in COMMAND_DESCRIPTIONS)
    lines = [
        "Observed command decoding:",
        "",
        "  The first character normally indicates the operation:",
        "    R = read",
        "    W = write",
        "    C = clear data",
        "",
        "  The second character normally identifies the operand area or",
        "  a special request type. Command names are case-sensitive.",
        "",
    ]
    for command, description in COMMAND_DESCRIPTIONS.items():
        lines.append(f"  {command:<{width}}  {description}")
    lines += [
        "",
        "Unknown commands are still recorded using their raw command and payload.",
    ]
    return "\n".join(lines)


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def xor_bcc(data):
    value = 0
    for byte in data:
        value ^= byte
    return value


def append_bcc(body):
    body = bytearray(body)
    body += f"{xor_bcc(body):02X}".encode("ascii")
    body += b"\r"
    return bytes(body)


def make_ack(data=b""):
    return append_bcc(b"\x06000" + data)


def make_rd_reply(addr, nbytes):
    words = nbytes // 2
    data = bytearray()
    for offset in range(words):
        value = D_VALUES.get(addr + offset, 0)
        data += f"{value & 0xFFFF:04X}".encode("ascii")
    if nbytes % 2:
        data += b"00"
    return make_ack(bytes(data))


def make_rm_reply(nbytes):
    return make_ack(b"0" * (nbytes * 8))


def make_timer_reply(count):
    return make_ack(b"0000" * max(count, 1))


def make_generic_read_reply(nbytes):
    return make_ack(b"00" * nbytes)


def make_write_reply():
    return make_ack()


def frame_text(frame):
    text = frame.decode("ascii", errors="backslashreplace")
    return text.replace("\r", "\\r")


def frame_hex(frame):
    return " ".join(f"{byte:02X}" for byte in frame)


def parse_hex_count(payload):
    if len(payload) < 6:
        return None
    try:
        return int(payload[4:6], 16)
    except ValueError:
        return None


def decimal_range(prefix, address, count):
    end = address + max(count - 1, 0)
    if end == address:
        return f"{prefix}{address}", str(end)
    return f"{prefix}{address}-{prefix}{end}", str(end)


@dataclass
class RequestRecord:
    access: str
    command: str
    operand: str
    register_range: str
    start_address: str
    end_address: str
    item_count: int
    item_unit: str
    request_bytes: int
    first_seen: str
    last_seen: str
    request_count: int
    valid_bcc: bool
    payload: str
    raw_request: str
    raw_hex: str

    def key(self):
        """Global logging key. Write data remains significant here."""
        return (
            self.access,
            self.command,
            self.start_address,
            self.end_address,
            self.item_count,
            self.item_unit,
            self.payload,
        )

    def live_key(self):
        """Key for the active read-command set; reply values never enter it."""
        selector = self.payload[:6] if len(self.payload) >= 6 else self.payload
        return self.command, selector

    def live_line(self):
        label = self.access.upper()
        if self.command == "Wm" and len(self.payload) >= 5:
            try:
                address = int(self.payload[:4], 10)
                return f"{label:5} {self.command}: M{address} = {self.payload[4:]}"
            except ValueError:
                pass

        line = f"{label:5} {self.command}: {self.register_range}"
        if self.access == "write" and len(self.payload) > 6:
            line += f" data={self.payload[6:]}"
        return line


def parse_request(frame):
    if len(frame) < 9 or frame[0] != 0x05 or not frame.endswith(b"\r"):
        return None

    command = frame[4:6].decode("ascii", errors="replace")
    payload_bytes = frame[6:-3]
    payload = payload_bytes.decode("ascii", errors="replace")
    received_bcc = frame[-3:-1].decode("ascii", errors="replace").upper()
    expected_bcc = f"{xor_bcc(frame[:-3]):02X}"
    valid_bcc = received_bcc == expected_bcc

    if command.startswith("R"):
        access = "read"
    elif command.startswith("W"):
        access = "write"
    else:
        access = "other"

    operand = command[1:2] if len(command) == 2 else ""
    start = ""
    end = ""
    item_count = 0
    item_unit = "unknown"
    request_bytes = 0
    register_range = f"{command} payload {payload}"

    if command == "Wm" and len(payload) >= 5:
        try:
            address = int(payload[:4], 10)
        except ValueError:
            address = None
        if address is not None:
            start = str(address)
            end = str(address)
            item_count = 1
            item_unit = "bit"
            register_range = f"M{address} = {payload[4:]}"

    count = parse_hex_count(payload)
    if count is not None:
        address_text = payload[:4]
        request_bytes = count

        if operand in ("D", "M", "_"):
            try:
                address = int(address_text, 10)
            except ValueError:
                address = None

            if address is not None:
                start = str(address)
                if operand == "D":
                    item_count = count // 2
                    item_unit = "words"
                    register_range, end = decimal_range("D", address, item_count)
                elif operand == "M":
                    item_count = count * 8
                    item_unit = "bits"
                    register_range, end = decimal_range("M", address, item_count)
                else:
                    item_count = count
                    item_unit = "timers"
                    register_range, end = decimal_range("T", address, item_count)

        elif operand == "A":
            try:
                address = int(address_text, 16)
            except ValueError:
                address = None

            start = address_text
            item_count = count // 2
            item_unit = "words"
            if address is None:
                register_range = f"A{address_text} ({count} bytes)"
            else:
                end_address = address + max(item_count - 1, 0)
                end = f"{end_address:X}"
                if end_address == address:
                    decoded = f"D{address}"
                else:
                    decoded = f"D{address}-D{end_address}"
                register_range = f"A{address_text} ({count} bytes): {decoded}"

        else:
            start = address_text
            item_count = count
            item_unit = "bytes"
            register_range = f"{operand}{address_text} ({count} bytes)"

    seen = now_iso()
    return RequestRecord(
        access=access,
        command=command,
        operand=operand,
        register_range=register_range,
        start_address=start,
        end_address=end,
        item_count=item_count,
        item_unit=item_unit,
        request_bytes=request_bytes,
        first_seen=seen,
        last_seen=seen,
        request_count=1,
        valid_bcc=valid_bcc,
        payload=payload,
        raw_request=frame_text(frame),
        raw_hex=frame_hex(frame),
    )


class RequestTracker:
    def __init__(
        self,
        output_path,
        quiet=False,
        append=False,
        flush_interval=1.0,
        detailed=False,
        terminal_output=True,
    ):
        self.output_path = Path(output_path)
        self.quiet = quiet
        self.append = append
        self.flush_interval = flush_interval
        self.detailed = detailed
        self.terminal_output = terminal_output
        self.records = {}
        self.compact_lines = set()
        self.last_flush = 0.0
        self.dirty = False

        if append and self.output_path.exists():
            if detailed:
                self._load_existing_csv()
            else:
                self._load_existing_compact()
        elif not detailed:
            self.output_path.parent.mkdir(parents=True, exist_ok=True)
            self.output_path.write_text("", encoding="utf-8")

    @staticmethod
    def display_line(record):
        return f"NEW {record.access.upper():5} {record.command}: {record.register_range}"

    def _load_existing_compact(self):
        try:
            with self.output_path.open(encoding="utf-8") as file:
                self.compact_lines = {
                    line.rstrip("\n") for line in file if line.strip()
                }
        except OSError as exc:
            print(f"Warning: could not load {self.output_path}: {exc}", file=sys.stderr)

    def _load_existing_csv(self):
        try:
            with self.output_path.open(newline="", encoding="utf-8") as file:
                for row in csv.DictReader(file):
                    record = RequestRecord(
                        access=row["access"],
                        command=row["command"],
                        operand=row["operand"],
                        register_range=row["register_range"],
                        start_address=row["start_address"],
                        end_address=row["end_address"],
                        item_count=int(row["item_count"]),
                        item_unit=row["item_unit"],
                        request_bytes=int(row["request_bytes"]),
                        first_seen=row["first_seen"],
                        last_seen=row["last_seen"],
                        request_count=int(row["request_count"]),
                        valid_bcc=row["valid_bcc"].lower() == "true",
                        payload=row["payload"],
                        raw_request=row["raw_request"],
                        raw_hex=row["raw_hex"],
                    )
                    self.records[record.key()] = record
        except (OSError, KeyError, ValueError, csv.Error) as exc:
            print(f"Warning: could not load {self.output_path}: {exc}", file=sys.stderr)

    def observe(self, record):
        key = record.key()
        existing = self.records.get(key)
        is_new = existing is None

        if is_new:
            self.records[key] = record
            line = self.display_line(record)
            if self.terminal_output and not self.quiet:
                print(line, flush=True)
            if not self.detailed and line not in self.compact_lines:
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
                with self.output_path.open("a", encoding="utf-8") as file:
                    file.write(line + "\n")
                self.compact_lines.add(line)
        else:
            existing.last_seen = record.last_seen
            existing.request_count += 1
            existing.valid_bcc = existing.valid_bcc and record.valid_bcc

        if self.detailed:
            self.dirty = True
        self.maybe_flush(force=is_new)
        return is_new

    def maybe_flush(self, force=False):
        if not self.detailed or not self.dirty:
            return
        now = time.monotonic()
        if force or now - self.last_flush >= self.flush_interval:
            self.flush()

    @staticmethod
    def _sort_address(record):
        if not record.start_address:
            return 10**9
        try:
            base = 16 if record.operand == "A" else 10
            return int(record.start_address, base)
        except ValueError:
            return 10**9

    def flush(self):
        if not self.detailed or not self.dirty:
            return

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        records = sorted(
            self.records.values(),
            key=lambda item: (
                item.access,
                item.operand,
                self._sort_address(item),
                item.command,
                item.payload,
            ),
        )

        with temp_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

        os.replace(temp_path, self.output_path)
        self.last_flush = time.monotonic()
        self.dirty = False


class LiveRequestMonitor:
    """Track the currently active read-command set without reply values."""

    def __init__(self, hold=2.0, debounce=0.15, warmup=2.0, quiet=False):
        self.hold = hold
        self.debounce = debounce
        self.warmup = warmup
        self.quiet = quiet
        self.started = time.monotonic()
        self.warmed = False
        self.active_reads = {}
        self.pending_added = OrderedDict()
        self.pending_removed = OrderedDict()
        self.pending_events = []
        self.last_change = 0.0

    @staticmethod
    def clear_screen():
        if sys.stdout.isatty():
            print("\033[2J\033[H", end="", flush=True)
        else:
            print("\n" + "=" * 72)

    def observe(self, record):
        if self.quiet:
            return

        now = time.monotonic()
        if record.access != "read":
            self.pending_events.append(record.live_line())
            self.last_change = now
            return

        key = record.live_key()
        existing = self.active_reads.get(key)
        self.active_reads[key] = (now, record.live_line())

        if existing is None and self.warmed:
            self.pending_added[key] = record.live_line()
            self.pending_removed.pop(key, None)
            self.last_change = now

    def tick(self, force=False):
        if self.quiet:
            return

        now = time.monotonic()
        if not self.warmed and now - self.started >= self.warmup:
            self.warmed = True
            self._render_baseline()

        expired = []
        for key, (last_seen, line) in self.active_reads.items():
            if now - last_seen > self.hold:
                expired.append((key, line))

        for key, line in expired:
            del self.active_reads[key]
            if self.warmed:
                if key in self.pending_added:
                    del self.pending_added[key]
                else:
                    self.pending_removed[key] = line
                self.last_change = now

        pending = self.pending_added or self.pending_removed or self.pending_events
        if pending and (force or now - self.last_change >= self.debounce):
            self._render_changes()

    def _render_baseline(self):
        self.clear_screen()
        print("HMI LIVE REQUEST MONITOR")
        print(f"Baseline learned: {len(self.active_reads)} active read commands")
        print("Read reply values are ignored.")
        print("Waiting for command-set changes or write events...", flush=True)

    def _render_changes(self):
        self.clear_screen()
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        print(f"HMI REQUEST CHANGE  {stamp}")
        print(f"Active read commands: {len(self.active_reads)}")
        print()

        if self.pending_added:
            print("ADDED READ REQUESTS")
            for line in self.pending_added.values():
                print(f"+ {line}")
            print()

        if self.pending_removed:
            print("REMOVED READ REQUESTS")
            for line in self.pending_removed.values():
                print(f"- {line}")
            print()

        if self.pending_events:
            print("WRITE / OTHER EVENTS")
            for line in self.pending_events:
                print(f"! {line}")
            print()

        print("Waiting for the next change...", flush=True)
        self.pending_added.clear()
        self.pending_removed.clear()
        self.pending_events.clear()


def debug_packet(label, frame, enabled):
    if not enabled:
        return
    print(f"{label} HEX: {frame_hex(frame)}")
    print(f"{label} ASCII: {frame!r}")


def reply_for_request(frame):
    if len(frame) < 9 or frame[0] != 0x05:
        return None

    command = frame[4:6]
    payload = frame[6:-3]

    if command.startswith(b"W"):
        return make_write_reply()

    if not command.startswith(b"R"):
        return None

    try:
        count = int(payload[4:6], 16) if len(payload) >= 6 else 0
    except ValueError:
        return None

    if command == b"RD":
        try:
            address = int(payload[:4], 10)
        except ValueError:
            return None
        return make_rd_reply(address, count)

    if command == b"RM":
        return make_rm_reply(count)

    if command == b"R_":
        return make_timer_reply(count)

    return make_generic_read_reply(count)


def handle(client, tracker, live_monitor=None, debug=False):
    buffer = b""
    if live_monitor is not None:
        client.settimeout(0.1)

    while True:
        try:
            chunk = client.recv(4096)
        except socket.timeout:
            live_monitor.tick()
            continue

        if not chunk:
            if live_monitor is not None:
                live_monitor.tick(force=True)
            return

        buffer += chunk
        while b"\r" in buffer:
            frame, buffer = buffer.split(b"\r", 1)
            frame += b"\r"
            debug_packet("RX", frame, debug)

            record = parse_request(frame)
            if record is not None:
                tracker.observe(record)
                if live_monitor is not None:
                    live_monitor.observe(record)

            reply = reply_for_request(frame)
            if reply is None:
                if debug:
                    print("No reply generated")
                continue

            debug_packet("TX", reply, debug)
            client.sendall(reply)

        if live_monitor is not None:
            live_monitor.tick()


def positive_float(value):
    number = float(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return number


def nonnegative_float(value):
    number = float(value)
    if number < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return number


def main():
    parser = argparse.ArgumentParser(
        description="Record and monitor IDEC HMI maintenance-protocol requests.",
        epilog=command_help_text(),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", default=PORT, type=int)
    parser.add_argument("--csv", default=DEFAULT_CSV)
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to an existing output file.",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Do not print terminal output.",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show RX/TX frames and write detailed CSV output.",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="Clear the terminal and show only command-set changes.",
    )

    parser.add_argument(
        "--live-hold",
        type=positive_float,
        default=2.0,
        metavar="SECONDS",
        help="Keep a read request active this long after its last poll (default: 2.0).",
    )
    parser.add_argument(
        "--live-debounce",
        type=nonnegative_float,
        default=0.15,
        metavar="SECONDS",
        help="Group rapid request changes before redrawing (default: 0.15).",
    )
    parser.add_argument(
        "--live-warmup",
        type=nonnegative_float,
        default=2.0,
        metavar="SECONDS",
        help="Learn the initial request set before reporting changes (default: 2.0).",
    )
    args = parser.parse_args()

    tracker = RequestTracker(
        output_path=args.csv,
        quiet=args.quiet,
        append=args.append,
        detailed=args.debug,
        terminal_output=not args.live,
    )
    live_monitor = None
    if args.live:
        live_monitor = LiveRequestMonitor(
            hold=args.live_hold,
            debounce=args.live_debounce,
            warmup=args.live_warmup,
            quiet=args.quiet,
        )

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((args.host, args.port))
        server.listen(4)
    except OSError as exc:
        print(
            f"Error: cannot listen on {args.host}:{args.port}: {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    if not args.quiet and not args.live:
        print(f"Listening on {args.host}:{args.port}")
        output_mode = "detailed CSV" if args.debug else "compact register list"
        print(f"Writing {output_mode} to {tracker.output_path}")
    elif not args.quiet:
        print(f"Listening on {args.host}:{args.port}")
        print(f"Logging unique requests to {tracker.output_path}")
        print("Learning the initial live request set...", flush=True)

    try:
        while True:
            client, address = server.accept()
            if args.debug:
                print(f"Connected: {address[0]}:{address[1]}")
            try:
                handle(
                    client,
                    tracker,
                    live_monitor=live_monitor,
                    debug=args.debug,
                )
            except (ConnectionError, OSError) as exc:
                if args.debug:
                    print(f"Connection ended: {exc}")
            finally:
                client.close()
                tracker.flush()
                if args.debug:
                    print("Disconnected")
    except KeyboardInterrupt:
        if not args.quiet:
            print("\nStopped")
    finally:
        if live_monitor is not None:
            live_monitor.tick(force=True)
        tracker.flush()
        server.close()


if __name__ == "__main__":
    main()
