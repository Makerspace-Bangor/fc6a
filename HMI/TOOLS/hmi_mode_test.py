#!/usr/bin/env python3
import argparse
import getpass
import socket
import time

HOST = "192.168.1.150"
PORT = 2537

MODE_NAMES = {
    1: "RUN / normal",
    2: "SYSTEM",
    3: "MONITOR",
    4: "SIMULATION",
    6: "DATA TRANSMISSION",
    7: "SYSTEM TRANSMISSION",
}


def xor_bcc(data):
    value = 0
    for byte in data:
        value ^= byte
    return value


def inner_command(command, payload=""):
    body = b"\x05" + b"00FF" + command.encode("ascii") + payload.encode("ascii")
    return body + f"{xor_bcc(body):02X}".encode("ascii") + b"\r"


def nv3_packet(inner):
    total = 18 + len(inner)
    if total > 0xFFFFFF:
        raise ValueError("packet too large")

    prefix = bytearray([
        0x01,
        (total >> 16) & 0xFF,
        (total >> 8) & 0xFF,
        total & 0xFF,
        0x00, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
        0x01, 0x01, 0x01,
    ])
    return bytes(prefix) + inner


def hexline(data):
    return " ".join(f"{b:02X}" for b in data)


def recv_packet(sock):
    data = b""

    while len(data) < 4:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("connection closed")
        data += chunk

    total = int.from_bytes(data[1:4], "big")

    while len(data) < total:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionError("connection closed")
        data += chunk

    return data[:total]


def unwrap(packet):
    if len(packet) < 18:
        return b""
    return packet[18:]


def show_reply(command, packet):
    inner = unwrap(packet)

    print(f"{command} RX: {hexline(packet)}")
    print(f"{command} inner: {inner!r}")

    if not inner:
        return

    if b"\x15" in inner:
        print(f"{command}: NAK")
    elif b"\x06" in inner or b"\x02" in inner:
        print(f"{command}: response received")


def transact(command, payload="", timeout=4.0):
    inner = inner_command(command, payload)
    packet = nv3_packet(inner)

    print()
    print(f"{command} payload: {payload!r}")
    print(f"{command} TX: {hexline(packet)}")
    print(f"{command} inner TX: {inner!r}")

    with socket.create_connection((ARGS.host, ARGS.port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        sock.sendall(packet)
        reply = recv_packet(sock)

    show_reply(command, reply)
    return reply


def parse_ab(packet):
    inner = unwrap(packet)

    # Normal observed reply form contains STX followed by:
    #     00FF + two ASCII decimal mode digits + ...
    stx = inner.find(b"\x02")
    if stx < 0:
        return None

    data = inner[stx + 1:]

    if data.startswith(b"00FF") and len(data) >= 6:
        mode_text = data[4:6]
        try:
            return int(mode_text.decode("ascii"), 10)
        except ValueError:
            pass

    return None


def query_mode():
    try:
        reply = transact("AB")
    except (OSError, ConnectionError) as exc:
        print(f"AB failed: {exc}")
        return None

    mode = parse_ab(reply)

    if mode is None:
        print("Could not decode mode from AB response.")
    else:
        print(f"Reported mode: {mode:02d} - {MODE_NAMES.get(mode, 'unknown')}")

    return mode


def change_mode(mode):
    name = MODE_NAMES.get(mode, "unknown")

    print()
    print(f"Requesting mode {mode:02d} - {name}")
    print("DLL DAPI_AA encoding: AA + two-digit hexadecimal mode.")

    try:
        transact("AA", f"{mode:02X}", timeout=10.0)
    except (OSError, ConnectionError) as exc:
        print(f"AA transaction ended with: {exc}")
        print("The DLL reconnects after AA, so a disconnect here may be expected.")

    print()
    print("Polling AB for the resulting mode...")

    deadline = time.monotonic() + ARGS.wait

    while time.monotonic() < deadline:
        mode_now = query_mode()

        if mode_now == mode:
            print(f"Mode change confirmed: {mode_now:02d} - {name}")
            return True

        time.sleep(ARGS.interval)

    print(f"Mode {mode:02d} was not confirmed within {ARGS.wait:g} seconds.")
    return False



def exit_system():
    print()
    print("Returning to RUN mode with AH...")

    try:
        transact("AH", timeout=10.0)
    except (OSError, ConnectionError) as exc:
        print(f"AH transaction ended with: {exc}")
        print("A disconnect may be expected while the HMI changes mode.")

    print()
    print("Waiting for the HMI to return to RUN mode...")

    deadline = time.monotonic() + ARGS.wait

    while time.monotonic() < deadline:
        mode_now = query_mode()

        if mode_now == 1:
            print("Return to RUN confirmed: 01 - RUN / normal")
            return True

        time.sleep(ARGS.interval)

    print(f"RUN mode was not confirmed within {ARGS.wait:g} seconds.")
    return False



def read_host_interfaces():
    print()
    print("Reading host-interface information with AM...")

    try:
        reply = transact("AM", timeout=185.0)
    except (OSError, ConnectionError) as exc:
        print(f"AM failed: {exc}")
        return

    inner = unwrap(reply)
    stx = inner.find(b"\x02")
    etx = inner.find(b"\x03", stx + 1) if stx >= 0 else -1

    if stx < 0:
        print("AM response did not contain STX.")
        return

    data = inner[stx + 1:etx if etx >= 0 else None]

    print()
    print(f"AM framed data length: {len(data)} bytes")
    print(f"AM framed data: {data!r}")

    # The NV3 response includes the normal "00FF" address prefix.
    if not data.startswith(b"00FF"):
        print("AM response does not begin with expected 00FF prefix.")
        return

    payload = data[4:]

    # DAPI_AM() receives a 170-character payload after protocol framing.
    # The first byte (two ASCII hex characters) is the interface count.
    # It then parses one 42-character record per interface:
    #
    #   Protocol1       2 ASCII hex chars
    #   Manufacturer    2 ASCII hex chars
    #   Protocol2       2 ASCII hex chars
    #   DriverVersion   4 chars
    #   reserved        32 chars
    #
    # Observed Linux HMI:
    #   04 + 4 * 42 = 170 characters.
    print(f"AM payload length after 00FF: {len(payload)} bytes")
    print(f"AM payload: {payload!r}")

    if len(payload) < 2:
        print("AM payload is too short.")
        return

    try:
        interface_count = int(payload[0:2].decode("ascii"), 16)
    except (UnicodeDecodeError, ValueError):
        print(f"Could not decode interface count from {payload[0:2]!r}")
        return

    print()
    print(f"Reported interface count: {interface_count}")

    pos = 2
    record_size = 42

    for index in range(interface_count):
        record = payload[pos:pos + record_size]

        if len(record) < record_size:
            print(f"Interface {index + 1}: truncated record ({len(record)} bytes)")
            break

        try:
            protocol1 = int(record[0:2].decode("ascii"), 16)
            manufacturer = int(record[2:4].decode("ascii"), 16)
            protocol2 = int(record[4:6].decode("ascii"), 16)
        except (UnicodeDecodeError, ValueError):
            print(f"Interface {index + 1}: could not decode record {record!r}")
            pos += record_size
            continue

        driver_version = record[6:10].decode("ascii", errors="replace")
        reserved = record[10:42]

        print()
        print(f"Interface {index + 1}:")
        print(f"  Raw record:     {record!r}")
        print(f"  Protocol1:      0x{protocol1:02X} ({protocol1})")
        print(f"  Manufacturer:   0x{manufacturer:02X} ({manufacturer})")
        print(f"  Protocol2:      0x{protocol2:02X} ({protocol2})")
        print(f"  DriverVersion:  {driver_version!r}")
        print(f"  Reserved:       {reserved!r}")

        pos += record_size

    trailing = payload[pos:]
    if trailing:
        print()
        print(f"Trailing payload bytes: {trailing!r}")




def read_user_system_information():
    print()
    print("Reading user/system information with AI...")

    try:
        reply = transact("AI", timeout=10.0)
    except (OSError, ConnectionError) as exc:
        print(f"AI failed: {exc}")
        return

    inner = unwrap(reply)
    stx = inner.find(b"\x02")
    etx = inner.find(b"\x03", stx + 1) if stx >= 0 else -1

    if stx < 0:
        print("AI response did not contain STX.")
        return

    data = inner[stx + 1:etx if etx >= 0 else None]

    print()
    print(f"AI framed data length: {len(data)} bytes")
    print(f"AI framed data: {data!r}")

    if not data.startswith(b"00FF"):
        print("AI response does not begin with expected 00FF prefix.")
        return

    payload = data[4:]

    print(f"AI payload length after 00FF: {len(payload)} bytes")
    print(f"AI payload: {payload!r}")

    # DAPI_AI() expects 540 characters after NV3 framing.
    # Parse only the initial fields whose offsets are explicit in the DLL.
    if len(payload) < 8:
        print("AI payload is too short to decode initial fields.")
        return

    try:
        driver_connection_type = int(payload[0:2].decode("ascii"), 10)
        protocol1 = int(payload[2:4].decode("ascii"), 16)
        manufacturer = int(payload[4:6].decode("ascii"), 16)
        protocol2 = int(payload[6:8].decode("ascii"), 16)
    except (UnicodeDecodeError, ValueError) as exc:
        print(f"Could not decode initial AI fields: {exc}")
        return

    print()
    print("Initial AI fields:")
    print(f"  Driver connection type: {driver_connection_type}")
    print(f"  Protocol1:              0x{protocol1:02X} ({protocol1})")
    print(f"  Manufacturer:           0x{manufacturer:02X} ({manufacturer})")
    print(f"  Protocol2:              0x{protocol2:02X} ({protocol2})")

    print()
    print("AI hex/ascii dump:")
    width = 32
    for offset in range(0, len(payload), width):
        chunk = payload[offset:offset + width]
        ascii_text = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        hex_text = " ".join(f"{b:02X}" for b in chunk)
        print(f"{offset:04X}  {hex_text:<95}  {ascii_text}")



def split_string_to_hex(value, length):
    result = ["0"] * length
    pos = 0

    for char in value:
        encoded = f"{ord(char):X}"
        if len(encoded) != 2:
            raise ValueError(
                f"AO helper expects one-byte characters; {char!r} encoded as {encoded}"
            )
        if pos + 2 > length:
            raise ValueError(f"value is too long for {length // 2}-byte field")
        result[pos] = encoded[0]
        result[pos + 1] = encoded[1]
        pos += 2

    return "".join(result)


def encrypt_password(password):
    shifted = "".join(chr((ord(char) << 1) & 0xFF) for char in password)
    return split_string_to_hex(shifted, 32)


def build_ao_payload(username, password, work_item):
    # DAPI_AO:
    #   username       32 ASCII hex chars
    #   reserved       32 ASCII hex chars
    #   password       32 ASCII hex chars
    #   reserved       32 ASCII hex chars
    #   WorkItem        8 ASCII hex chars
    username_hex = split_string_to_hex(username, 32)
    reserved = "0" * 32
    password_hex = encrypt_password(password)
    return (
        username_hex
        + reserved
        + password_hex
        + reserved
        + f"{work_item:08X}"
    )


def recv_and_show(sock, command):
    reply = recv_packet(sock)
    show_reply(command, reply)
    return reply


def send_on_socket(sock, command, payload="", timeout=10.0):
    inner = inner_command(command, payload)
    packet = nv3_packet(inner)

    print()
    print(f"{command} payload: {payload!r}")
    print(f"{command} TX: {hexline(packet)}")
    print(f"{command} inner TX: {inner!r}")

    sock.settimeout(timeout)
    sock.sendall(packet)
    return recv_and_show(sock, command)


def is_ack(packet):
    inner = unwrap(packet)
    return b"\x06" in inner and b"\x15" not in inner


def ao_then_mode(work_item, mode):
    username = input("Username [User]: ").strip() or "User"
    password = getpass.getpass("Password: ")

    try:
        payload = build_ao_payload(username, password, work_item)
    except ValueError as exc:
        print(f"Could not build AO payload: {exc}")
        return False

    print()
    print(
        f"Authenticating with AO for WorkItem 0x{work_item:08X}, "
        f"then requesting mode {mode:02d} on the same TCP connection..."
    )

    try:
        with socket.create_connection((ARGS.host, ARGS.port), timeout=10.0) as sock:
            ao_reply = send_on_socket(sock, "AO", payload, timeout=10.0)

            if not is_ack(ao_reply):
                print("AO did not ACK; mode command will not be sent.")
                return False

            print("AO acknowledged.")

            try:
                send_on_socket(sock, "AA", f"{mode:02X}", timeout=10.0)
            except (OSError, ConnectionError) as exc:
                print(f"AA transaction ended with: {exc}")
                print("A disconnect may be expected while changing HMI mode.")

    except (OSError, ConnectionError) as exc:
        print(f"AO connection failed: {exc}")
        return False

    print()
    print("Polling AB for the resulting mode...")

    deadline = time.monotonic() + ARGS.wait

    while time.monotonic() < deadline:
        mode_now = query_mode()
        if mode_now == mode:
            print(f"Authenticated mode change confirmed: {mode:02d}")
            return True
        time.sleep(ARGS.interval)

    print(f"Mode {mode:02d} was not confirmed within {ARGS.wait:g} seconds.")
    return False


def ao_then_dl():
    username = input("Username [User]: ").strip() or "User"
    password = getpass.getpass("Password: ")
    screen_text = input("Screen number [3]: ").strip() or "3"

    try:
        screen = int(screen_text, 0)
    except ValueError:
        print("Invalid screen number.")
        return False

    if not 0 <= screen <= 0xFFFF:
        print("Screen number must be 0-65535.")
        return False

    work_item = 0x00004000

    try:
        payload = build_ao_payload(username, password, work_item)
    except ValueError as exc:
        print(f"Could not build AO payload: {exc}")
        return False

    print()
    print(
        f"Authenticating with AO for WorkItem 0x{work_item:08X}, "
        f"then sending DL {screen:04X} on the same TCP connection..."
    )

    try:
        with socket.create_connection((ARGS.host, ARGS.port), timeout=10.0) as sock:
            ao_reply = send_on_socket(sock, "AO", payload, timeout=10.0)

            if not is_ack(ao_reply):
                print("AO did not ACK; DL will not be sent.")
                return False

            print("AO acknowledged.")
            dl_reply = send_on_socket(sock, "DL", f"{screen:04X}", timeout=10.0)

            if is_ack(dl_reply):
                print(f"DL {screen:04X} acknowledged after AO.")
                return True

            print(f"DL {screen:04X} was not acknowledged after AO.")
            return False

    except (OSError, ConnectionError) as exc:
        print(f"AO/DL transaction failed: {exc}")
        return False


def raw_aa():
    value = input("AA mode byte, hex (00-FF): ").strip()

    try:
        mode = int(value, 16)
    except ValueError:
        print("Invalid hexadecimal byte.")
        return

    if not 0 <= mode <= 0xFF:
        print("Mode must be 00-FF.")
        return

    change_mode(mode)


def menu():
    while True:
        print()
        print("IDEC HMI mode tester")
        print("--------------------")
        print("1) Query current mode (AB)")
        print("2) RUN / normal             AA 01")
        print("3) SYSTEM                   AA 02")
        print("4) MONITOR                  AA 03")
        print("5) SIMULATION               AA 04")
        print("6) DATA TRANSMISSION        AA 06")
        print("7) SYSTEM TRANSMISSION      AA 07")
        print("8) Exit system / return RUN  AH")
        print("9) Raw AA mode byte")
        print("10) Read host-interface information  AM")
        print("11) Read user/system information     AI")
        print("12) AO auth -> MONITOR AA03  WorkItem 0x00004000")
        print("13) AO auth -> SYSTEM  AA02  WorkItem 0x00002000")
        print("14) AO auth -> DL screen      WorkItem 0x00004000")
        print("q) Quit")
        print()

        choice = input("Selection: ").strip().lower()

        if choice == "1":
            query_mode()
        elif choice == "2":
            change_mode(1)
        elif choice == "3":
            change_mode(2)
        elif choice == "4":
            change_mode(3)
        elif choice == "5":
            change_mode(4)
        elif choice == "6":
            change_mode(6)
        elif choice == "7":
            change_mode(7)
        elif choice == "8":
            exit_system()
        elif choice == "9":
            raw_aa()
        elif choice == "10":
            read_host_interfaces()
        elif choice == "11":
            read_user_system_information()
        elif choice == "12":
            ao_then_mode(0x00004000, 3)
        elif choice == "13":
            ao_then_mode(0x00002000, 2)
        elif choice == "14":
            ao_then_dl()
        elif choice in ("q", "quit", "exit"):
            return
        else:
            print("Unknown selection.")


def main():
    global ARGS

    parser = argparse.ArgumentParser(
        description="Interactively query/change IDEC HMI operating mode."
    )
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument(
        "--wait",
        type=float,
        default=15.0,
        help="seconds to poll AB after AA (default: 15)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="AB polling interval in seconds (default: 1)",
    )
    ARGS = parser.parse_args()

    print(f"Target: {ARGS.host}:{ARGS.port}")
    query_mode()
    menu()


if __name__ == "__main__":
    main()
