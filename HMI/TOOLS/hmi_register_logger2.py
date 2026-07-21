#!/usr/bin/env python3
"""
A utility to detect what the HMI is requesting.

The HMI connects to this program as though it were its configured PLC. 
Read requests receive zero-filled replies so it doesnt interact with 
the PC as though it were a PLC. Requests are written as compact lines by request. 
With --debug, the output file presents framing detailed CSV format. 
Write requests are recorded and acknowledged, but are NOT forwarded to a real PLC.

Example:
    python3 hmi_register_logger2.py --host 0.0.0.0 --port 2101 --csv hmi_registers.txt

Useful modes:
    --quiet       Do not print to the terminal.
    --debug       Print RX/TX frames and write the detailed CSV format.
    --help        prints response interpretations, as I learn more about 
                  which commands mean which opertations. 
                    
    --append      Append to an existing output file.
    --csv         output to a specified csv file
                  Without this flag, output is sent to hmi_registers.txt

$python3 hmi_register_logger2.py  --host 0.0.0.0 --port 2101 

"""

import argparse
import csv
import os
import socket
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path


HOST = "0.0.0.0"
PORT = 2101
DEFAULT_CSV = "hmi_registers.txt"


# Command descriptions shown by --help.
#
# Keep these descriptions conservative: several operand selectors have only
# been observed in HMI traffic and are not fully documented yet.
#
# Add future definitions with one line:
#     "WM": "Write M internal relay bits.",
COMMAND_DESCRIPTIONS = {
    "RD": "Read D data registers (16-bit words).",
    "RM": "Read M internal relay bits.",
    "RA": "Read A operand data; exact A-area meaning is not yet documented.",
    "R_": "Read Timer register: R_ 0 read timer register 0",
    "WD": "Write D data register(s).",
    "WM": "Write M internal relay bit(s).",
    "Wm": "Observed lowercase-m write; exact format is not yet documented.",
    "Rl": "Observed lowercase-l read; exact operand meaning is not documented.",
}


def command_help_text():
    width = max(len(command) for command in COMMAND_DESCRIPTIONS)
    lines = [
        "Observed command decoding:",
        "",
        "  The first character normally indicates the operation:",
        "    R = read",
        "    W = write",
        "    C = Clear data",
        "",
        "  The second character normally identifies the operand area or",
        "  a special request type. Command names are case-sensitive.",
        "",
    ]

    for command, description in COMMAND_DESCRIPTIONS.items():
        lines.append(f"    {command:<{width}}  {description}")

    lines += [
        "",
        "  Unknown commands are still recorded using their raw command and",
        "  payload. Add or edit entries in COMMAND_DESCRIPTIONS as more",
        "  protocol commands are identified.",
    ]
    return "\n".join(lines)

# Preserve the only nonzero value from the original emulator.
D_VALUES = {
    570: 26,
}


def now_iso():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def xor_bcc(data):
    value = 0
    for byte in data:
        value ^= byte
    return value


def append_bcc(body):
    body = bytearray(body)
    body += f"{xor_bcc(body):02X}".encode()
    body += b"\r"
    return bytes(body)


def make_ack(data=b""):
    return append_bcc(b"\x06000" + data)


def make_rd_reply(addr, nbytes):
    words = nbytes // 2
    data = bytearray()

    for offset in range(words):
        value = D_VALUES.get(addr + offset, 0)
        data += f"{value & 0xFFFF:04X}".encode()

    # If an odd byte count ever appears, preserve the requested reply length.
    if nbytes % 2:
        data += b"00"

    return make_ack(bytes(data))


def make_rm_reply(nbytes):
    # Preserve the behavior of the working emulator: one ASCII zero per bit.
    return make_ack(b"0" * (nbytes * 8))


def make_r_Reply(count):
    # Observed HMI requests use count=1. Return one zero word per requested item.
    return make_ack(b"0000" * max(count, 1))


def make_generic_read_reply(nbytes):
    return make_ack(b"00" * nbytes)


def make_write_reply():
    # Generic successful write acknowledgement.
    return make_ack()


def frame_text(frame):
    return frame.decode("ascii", errors="backslashreplace").replace("\r", "\\r")


def frame_hex(frame):
    return " ".join(f"{byte:02X}" for byte in frame)


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
        return (
            self.access,
            self.command,
            self.start_address,
            self.end_address,
            self.item_count,
            self.item_unit,
            self.payload,
        )


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


def parse_request(frame):
    if len(frame) < 9 or frame[0] != 0x05 or not frame.endswith(b"\r"):
        return None

    command = frame[4:6].decode("ascii", errors="replace")
    payload_bytes = frame[6:-3]
    payload = payload_bytes.decode("ascii", errors="replace")

    received_bcc = frame[-3:-1].decode("ascii", errors="replace").upper()
    expected_bcc = f"{xor_bcc(frame[:-3]):02X}"
    valid_bcc = received_bcc == expected_bcc

    access = "read" if command.startswith("R") else \
        "write" if command.startswith("W") else "other"
    operand = command[1:2] if len(command) == 2 else ""

    start = ""
    end = ""
    item_count = 0
    item_unit = "unknown"
    request_bytes = 0
    register_range = f"{command} payload {payload}"

    if len(payload) >= 6:
        try:
            address = int(payload[:4], 10)
            count = int(payload[4:6], 16)
            start = str(address)
            request_bytes = count

            if operand == "D":
                item_count = count // 2
                item_unit = "words"
                end_addr = address + item_count - 1 if item_count else address
                end = str(end_addr)
                register_range = (
                    f"D{address}" if end_addr == address
                    else f"D{address}-D{end_addr}"
                )

            elif operand == "M":
                item_count = count * 8
                item_unit = "bits"
                end_addr = address + item_count - 1 if item_count else address
                end = str(end_addr)
                register_range = (
                    f"M{address}" if end_addr == address
                    else f"M{address}-M{end_addr}"
                )

            elif operand == "_":
                item_count = count
                item_unit = "special-items"
                end_addr = address + item_count - 1 if item_count else address
                end = str(end_addr)
                register_range = (
                    f"R_ {address}" if end_addr == address
                    else f"R_ {address}-{end_addr}"
                )

            else:
                # Operand width is not assumed for RA or other command types.
                item_count = count
                item_unit = "bytes"
                register_range = f"{operand}{address} ({count} bytes)"

        except ValueError:
            pass

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
    ):
        self.output_path = Path(output_path)
        self.quiet = quiet
        self.append = append
        self.flush_interval = flush_interval
        self.detailed = detailed
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
            self.output_path.write_text('', encoding='utf-8')

    @staticmethod
    def display_line(record):
        return (
            f"NEW {record.access.upper():5} {record.command}: "
            f"{record.register_range}"
        )

    def _load_existing_compact(self):
        try:
            with self.output_path.open(encoding='utf-8') as file:
                self.compact_lines = {
                    line.rstrip('\n') for line in file if line.strip()
                }
        except OSError as exc:
            print(
                f"Warning: could not load {self.output_path}: {exc}",
                file=sys.stderr,
            )

    def _load_existing_csv(self):
        try:
            with self.output_path.open(newline='', encoding='utf-8') as file:
                for row in csv.DictReader(file):
                    record = RequestRecord(
                        access=row['access'],
                        command=row['command'],
                        operand=row['operand'],
                        register_range=row['register_range'],
                        start_address=row['start_address'],
                        end_address=row['end_address'],
                        item_count=int(row['item_count']),
                        item_unit=row['item_unit'],
                        request_bytes=int(row['request_bytes']),
                        first_seen=row['first_seen'],
                        last_seen=row['last_seen'],
                        request_count=int(row['request_count']),
                        valid_bcc=row['valid_bcc'].lower() == 'true',
                        payload=row['payload'],
                        raw_request=row['raw_request'],
                        raw_hex=row['raw_hex'],
                    )
                    self.records[record.key()] = record
        except (OSError, KeyError, ValueError, csv.Error) as exc:
            print(
                f"Warning: could not load {self.output_path}: {exc}",
                file=sys.stderr,
            )

    def observe(self, record):
        key = record.key()
        existing = self.records.get(key)
        is_new = existing is None

        if is_new:
            self.records[key] = record
            line = self.display_line(record)

            if not self.quiet:
                print(line, flush=True)

            if not self.detailed and line not in self.compact_lines:
                self.output_path.parent.mkdir(parents=True, exist_ok=True)
                with self.output_path.open('a', encoding='utf-8') as file:
                    file.write(line + '\n')
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

    def flush(self):
        if not self.detailed or not self.dirty:
            return

        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.output_path.with_suffix(
            self.output_path.suffix + '.tmp'
        )

        records = sorted(
            self.records.values(),
            key=lambda item: (
                item.access,
                item.operand,
                int(item.start_address) if item.start_address else 10**9,
                item.command,
                item.payload,
            ),
        )

        with temp_path.open('w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

        os.replace(temp_path, self.output_path)
        self.last_flush = time.monotonic()
        self.dirty = False


def debug_packet(label, frame, enabled):
    if not enabled:
        return

    print(f"{label} HEX:   {frame_hex(frame)}")
    print(f"{label} ASCII: {frame!r}")


def reply_for_request(frame):
    if len(frame) < 14 or frame[0] != 0x05:
        return None

    command = frame[4:6]
    payload = frame[6:-3]

    try:
        address = int(payload[:4], 10) if len(payload) >= 4 else 0
        count = int(payload[4:6], 16) if len(payload) >= 6 else 0
    except ValueError:
        return None

    if command == b"RD":
        return make_rd_reply(address, count)

    if command == b"RM":
        return make_rm_reply(count)

    if command == b"R_":
        return make_r_Reply(count)

    if command.startswith(b"R"):
        return make_generic_read_reply(count)

    if command.startswith(b"W"):
        return make_write_reply()

    return None


def handle(client, tracker, debug=False):
    buffer = b""

    while True:
        chunk = client.recv(4096)
        if not chunk:
            return

        buffer += chunk

        while b"\r" in buffer:
            frame, buffer = buffer.split(b"\r", 1)
            frame += b"\r"

            debug_packet("RX", frame, debug)

            record = parse_request(frame)
            if record is not None:
                tracker.observe(record)

            reply = reply_for_request(frame)
            if reply is None:
                if debug:
                    print("No reply generated")
                continue

            debug_packet("TX", reply, debug)
            client.sendall(reply)


def main():
    parser = argparse.ArgumentParser(
        description="Record unique IDEC HMI register requests.",
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
        help="Do not print newly discovered requests.",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="store_true",
        help="Show frames and write the full detailed CSV format.",
    )
    args = parser.parse_args()

    tracker = RequestTracker(
        output_path=args.csv,
        quiet=args.quiet,
        append=args.append,
        detailed=args.debug,
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

    if not args.quiet:
        print(f"Listening on {args.host}:{args.port}")
        mode = "detailed CSV" if args.debug else "compact register list"
        print(f"Writing {mode} to {tracker.output_path}")

    try:
        while True:
            client, address = server.accept()

            if args.debug:
                print(f"Connected: {address[0]}:{address[1]}")

            try:
                handle(client, tracker, debug=args.debug)
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
        tracker.flush()
        server.close()


if __name__ == "__main__":
    main()
