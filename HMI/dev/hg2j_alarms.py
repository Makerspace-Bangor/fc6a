#!/usr/bin/env python3

import argparse
import socket
import sys

HEADER_LEN = 18

DEVICE_IDS = {
    "LSM": 0x7A,
    "LSD": 0xF5,
}

SCRIPT_ERRORS = {
    1: "processing error",
    2: "execution time over error",
    3: "writing count error",
    4: "indirect device error",
    5: "parameter error",
    6: "fixed interval script execution time over",
    7: "fixed interval execution error",
}

MEMORY_ERRORS = {
    1: "write attempted with no/incompatible external memory",
    2: "format error",
    3: "access error, insufficient space, or read/write failure",
    4: "picture data read failure",
}

SNTP_RESULTS = {
    0: "success",
    2: "timeout error",
    4: "other error",
}

EMAIL_RESULTS = {
    0: "success",
    1: "parameter error",
    2: "timeout error",
    3: "authentication error",
    4: "other error",
}

# Only fixed HMI internal devices with useful diagnostic meaning are registered.
# Nothing in this script writes to the HMI.
DEVICES = [
    "LSD13",   # RTC year, BCD
    "LSD14",   # RTC month, BCD
    "LSD15",   # RTC day, BCD
    "LSD16",   # RTC hour, BCD
    "LSD17",   # RTC minute, BCD
    "LSD18",   # RTC second, BCD
    "LSD19",   # RTC day of week, BCD 0=Sunday
    "LSD31",   # Currently displayed screen number
    "LSM22",   # Operation-log overflow
    "LSM33",   # Too many drawings/parts on top layer
    "LSD29",   # Last SNTP execution result
    "LSD42",   # External memory error status (HG2J USB1)
    "LSD52",   # Script ID associated with LSD53
    "LSD53",   # Script error status
    "LSD67",   # User Communication TCP connection state
    "LSD97",   # Sound ID that could not be played
    "LSD222",  # Last e-mail send result
    "LSD227",  # Monitor/maintenance/pass-through TCP-port state
    "LSD231",  # FTP client transfer success count
    "LSD232",  # FTP client transfer failure count
]


def checksum(data):
    value = 0
    for byte in data:
        value ^= byte
    return value


def inner_command(text):
    data = b"\x05" + text.encode("ascii")
    return data + f"{checksum(data):02X}".encode("ascii") + b"\r"


def nv3_frame(data):
    total = HEADER_LEN + len(data)
    header = bytes([
        0x01, 0x00,
        (total >> 8) & 0xFF, total & 0xFF,
        0x00, 0x01,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x01, 0x01, 0x01,
    ])
    return header + data


def recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise ConnectionError("HMI closed connection")
        data.extend(chunk)
    return bytes(data)


def recv_frame(sock):
    first = recv_exact(sock, 4)
    total = int.from_bytes(first[2:4], "big")
    if total < 4:
        raise ValueError(f"invalid NV3 frame length {total}")
    return first + recv_exact(sock, total - 4)


def frame_payload(frame):
    if len(frame) < HEADER_LEN:
        return b""
    return frame[HEADER_LEN:]


def send_command(sock, text, debug=False):
    tx = nv3_frame(inner_command(text))

    if debug:
        print(f"TX {text}")
        print("   " + tx.hex(" "))

    sock.sendall(tx)
    rx = recv_frame(sock)

    if debug:
        print("RX")
        print("   " + rx.hex(" "))

    return rx


def parse_device(name):
    kind = name[:3]
    number = int(name[3:])

    return {
        "name": name,
        "port": 0x00,
        "device_id": DEVICE_IDS[kind],
        "bit": 0xFF,
        # The observed NV4 CG protocol encodes the printed device number as
        # hexadecimal digits. LSD227 therefore uses address field 00000227.
        "address": int(str(number), 16),
    }


def make_cg(reg, devices):
    fields = []

    for dev in devices:
        fields.append(
            f"{dev['port']:02X}"
            f"{dev['device_id']:02X}"
            f"{dev['bit']:02X}"
            f"{dev['address']:08X}"
        )

    return f"00FFCG{reg:02X}{len(devices):02X}" + "".join(fields)


def make_ch(reg):
    return f"00FFCH{reg:02X}"


def ack_status(frame):
    data = frame_payload(frame)

    if not data:
        return "empty response"

    if data[0] == 0x06:
        return "ACK"

    if data[0] == 0x15:
        rest = data[1:].rstrip(b"\r").decode("ascii", "replace")
        return f"NAK {rest}"

    return "unexpected response"


def parse_ch(frame, devices):
    data = frame_payload(frame)

    if data and data[0] == 0x15:
        return None

    try:
        stx = data.index(0x02)
        etx = data.index(0x03, stx + 1)
    except ValueError:
        return None

    body = data[stx + 1:etx]
    needed = len(devices) * 4

    if len(body) < needed:
        return None

    raw_values = body[-needed:]
    values = {}

    for index, dev in enumerate(devices):
        raw = raw_values[index * 4:(index + 1) * 4]

        if b"?" in raw:
            values[dev["name"]] = None
            continue

        try:
            values[dev["name"]] = int(raw.decode("ascii"), 16)
        except ValueError:
            return None

    return values



MODE_NAMES = {
    0x01: "RUN",
    0x02: "SYSTEM",
    0x03: "MONITOR",
    0x04: "SIMULATION",
    0x07: "SYSTEM TRANSMISSION",
}

WEEKDAYS = [
    "Sunday",
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
]


def parse_ab_mode(frame):
    data = frame_payload(frame)

    try:
        stx = data.index(0x02)
        etx = data.index(0x03, stx + 1)
    except ValueError:
        return None

    body = data[stx + 1:etx]

    # Observed AB reply body is 00FFxx, where xx is the mode byte in
    # two ASCII hexadecimal digits.
    if len(body) < 6:
        return None

    try:
        return int(body[-2:].decode("ascii"), 16)
    except ValueError:
        return None


def read_mode(sock, debug=False):
    reply = send_command(sock, "00FFAB", debug)
    value = parse_ab_mode(reply)

    if value is None:
        return None, "unknown"

    return value, MODE_NAMES.get(value, f"UNKNOWN 0x{value:02X}")


def bcd_text(value, digits):
    if value is None:
        return None

    text = f"{value:0{digits}X}"[-digits:]

    if any(ch not in "0123456789" for ch in text):
        return None

    return text


def hmi_datetime(values):
    year = bcd_text(values.get("LSD13"), 4)
    month = bcd_text(values.get("LSD14"), 2)
    day = bcd_text(values.get("LSD15"), 2)
    hour = bcd_text(values.get("LSD16"), 2)
    minute = bcd_text(values.get("LSD17"), 2)
    second = bcd_text(values.get("LSD18"), 2)

    if None in (year, month, day, hour, minute, second):
        return None

    weekday_value = values.get("LSD19")
    weekday = None

    if weekday_value is not None and 0 <= weekday_value < len(WEEKDAYS):
        weekday = WEEKDAYS[weekday_value]

    stamp = f"{year}-{month}-{day} {hour}:{minute}:{second}"

    if weekday:
        stamp += f" ({weekday})"

    return stamp



def issue(level, source, message):
    return {
        "level": level,
        "source": source,
        "message": message,
    }


def decode(values):
    active = []
    history = []

    if values.get("LSM22"):
        active.append(issue(
            "FAULT",
            "LSM22",
            "operation log overflow: one operation produced more data than can be recorded",
        ))

    if values.get("LSM33"):
        active.append(issue(
            "FAULT",
            "LSM33",
            "number of drawings/parts on the top layer exceeded the supported limit",
        ))

    value = values.get("LSD42")
    if value not in (None, 0):
        text = MEMORY_ERRORS.get(value, f"unknown error code {value}")
        active.append(issue("FAULT", "LSD42", f"external memory error: {text}"))

    script_error = values.get("LSD53")
    if script_error not in (None, 0):
        script_id = values.get("LSD52")
        text = SCRIPT_ERRORS.get(script_error, f"unknown script error {script_error}")
        suffix = f" in script {script_id}" if script_id not in (None, 0) else ""
        active.append(issue("FAULT", "LSD52/LSD53", f"script {text}{suffix}"))

    sntp = values.get("LSD29")
    if sntp not in (None, 0):
        text = SNTP_RESULTS.get(sntp, f"unknown result code {sntp}")
        history.append(issue("LAST", "LSD29", f"SNTP request: {text}"))

    sound_id = values.get("LSD97")
    if sound_id not in (None, 0):
        history.append(issue(
            "LAST",
            "LSD97",
            f"sound file ID {sound_id} could not be played",
        ))

    email = values.get("LSD222")
    if email not in (None, 0):
        text = EMAIL_RESULTS.get(email, f"unknown result code {email}")
        history.append(issue("LAST", "LSD222", f"e-mail send result: {text}"))

    ftp_failures = values.get("LSD232")
    if ftp_failures not in (None, 0):
        successes = values.get("LSD231")
        if successes is None:
            text = f"FTP client file-transfer failures: {ftp_failures}"
        else:
            text = (
                f"FTP client file-transfer failures: {ftp_failures} "
                f"(successes in same transfer run: {successes})"
            )
        history.append(issue("COUNT", "LSD231/LSD232", text))

    return active, history


def describe_status(values):
    status = []

    user = values.get("LSD67")
    if user is not None:
        channels = []
        for bit in range(3):
            state = "connected" if user & (1 << bit) else "disconnected"
            channels.append(f"User Communication {bit + 1}: {state}")
        status.extend(channels)

    ports = values.get("LSD227")
    if ports is not None:
        status.append(
            "WindO/I monitor: " + ("in use" if ports & 0x01 else "not in use")
        )
        status.append(
            "maintenance TCP 2537: " + ("in use" if ports & 0x02 else "not in use")
        )
        status.append(
            "pass-through TCP: " + ("in use" if ports & 0x04 else "not in use")
        )

    return status


def print_item(item, verbose, values):
    print(f"{item['level']}: {item['message']}")
    if verbose:
        sources = item["source"].split("/")
        raw = []

        for source in sources:
            value = values.get(source)
            if value is None:
                raw.append(f"{source}=?")
            else:
                raw.append(f"{source}={value} (0x{value:04X})")

        print("       " + "  ".join(raw))


def print_report(host, values, mode_name, verbose=False):
    active, history = decode(values)

    print(f"HG2J diagnostic report - {host}")
    print()

    print("HMI STATUS")
    print(f"Mode:       {mode_name}")

    screen = values.get("LSD31")
    if screen is None:
        print("Screen:     unknown")
    else:
        print(f"Screen:     {screen}")

    stamp = hmi_datetime(values)
    print(f"Date/time:  {stamp if stamp else 'unknown'}")
    print("Time zone:  project setting; not exposed by documented LSD registers")
    print("Battery:    no battery status register documented for HG2J-7U")
    print()

    if active:
        print("ACTIVE ISSUES")
        for item in active:
            print_item(item, verbose, values)
    else:
        print("ACTIVE ISSUES")
        print("None found in the fixed diagnostic devices checked.")

    if history:
        print()
        print("LAST ERROR / COUNTERS")
        for item in history:
            print_item(item, verbose, values)

    if verbose:
        print()
        print("STATUS")
        for line in describe_status(values):
            print(line)

        print()
        print("RAW DIAGNOSTIC VALUES")
        for name in DEVICES:
            value = values.get(name)
            if value is None:
                print(f"{name:6s} ?")
            else:
                print(f"{name:6s} {value:5d}  0x{value:04X}")

    print()
    print(f"{len(active)} active issue(s), {len(history)} historical/counter item(s)")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Read and decode known HG2J HMI internal diagnostic devices"
    )
    parser.add_argument(
        "host",
        nargs="?",
        default="192.168.1.150",
        help="HMI IP address (default: 192.168.1.150)",
    )
    parser.add_argument("--port", type=int, default=2537)
    parser.add_argument("--reg", type=lambda value: int(value, 0), default=1)
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show status and raw values for diagnostic devices",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="show complete TX/RX packet hex dumps",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not 1 <= args.reg <= 0xFF:
        print("error: --reg must be 1..255", file=sys.stderr)
        return 2

    devices = [parse_device(name) for name in DEVICES]

    try:
        with socket.create_connection((args.host, args.port), timeout=3.0) as sock:
            sock.settimeout(3.0)

            _, mode_name = read_mode(sock, args.debug)

            reply = send_command(sock, make_cg(args.reg, devices), args.debug)
            status = ack_status(reply)

            if status != "ACK":
                print(f"HG2J registration failed: {status}", file=sys.stderr)
                return 1

            reply = send_command(sock, make_ch(args.reg), args.debug)
            values = parse_ch(reply, devices)

            if values is None:
                print("Could not parse HG2J diagnostic values.", file=sys.stderr)
                return 1

    except (OSError, ConnectionError, ValueError) as exc:
        print(f"HG2J connection error: {exc}", file=sys.stderr)
        return 1

    print_report(args.host, values, mode_name, args.verbose)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
