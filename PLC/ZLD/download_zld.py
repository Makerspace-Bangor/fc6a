#!/usr/bin/env python3
"""
FC6A ZLD user-program downloader.

Observed program-only ZLD layout:

    descriptor @ 0x14: type 0x10 -> WPn
    descriptor @ 0x2C: type 0x11 -> W;n

Each descriptor is six little-endian uint32 values:

    type, file_offset, length, metadata, reserved1, reserved2

The script validates the section boundaries before sending anything.

No firmware-transfer path is implemented.

Examples:
    python download_zld.py program.zld
    python download_zld.py program.zld --port COM4
    python download_zld.py program.zld --inspect
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
import re
import struct
import time
from dataclasses import dataclass
from pathlib import Path

import serial

from MiSmSerial import MiSmSerial


PORT = "COM3" if os.name == "nt" else "/dev/ttyACM0"
BAUD = 9600
DEVICE = "FF"

BASE_ADDR = "600000"
BLOCK_SIZE = 736

RA = "FF0RA1FB804"
RU = "FF0Ru12"

SER_TIMEOUT = 0.05
REPLY_TIMEOUT = 5.0
RU_TRIES = 12
RU_DELAY = 1.0

ENQ = 0x05
ACK = 0x06
NAK = 0x15
CR = 0x0D

DESC_PN = 0x14
DESC_AUX = 0x2C
TYPE_PN = 0x10
TYPE_AUX = 0x11


@dataclass(frozen=True)
class Section:
    type_id: int
    offset: int
    length: int
    metadata: int
    reserved1: int
    reserved2: int

    @property
    def end(self) -> int:
        return self.offset + self.length


@dataclass(frozen=True)
class ZLD:
    data: bytes
    size_field: int
    pn: Section
    aux: Section

    def bytes_for(self, section: Section) -> bytes:
        return self.data[section.offset:section.end]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def descriptor(data: bytes, offset: int) -> Section:
    if offset + 24 > len(data):
        raise ValueError(f"descriptor at 0x{offset:X} is outside the file")
    return Section(*struct.unpack_from("<6I", data, offset))


def parse_zld(data: bytes) -> ZLD:
    if len(data) < 72:
        raise ValueError(f"ZLD is too short: {len(data)} bytes")

    size_field = struct.unpack_from("<I", data, 0x10)[0]
    d0 = descriptor(data, DESC_PN)
    d1 = descriptor(data, DESC_AUX)
    sections = {d0.type_id: d0, d1.type_id: d1}

    if TYPE_PN not in sections or TYPE_AUX not in sections:
        raise ValueError(
            "unsupported ZLD descriptors: expected types 0x10 and 0x11, "
            f"found 0x{d0.type_id:X} and 0x{d1.type_id:X}"
        )

    pn = sections[TYPE_PN]
    aux = sections[TYPE_AUX]
    errors = []

    if pn.offset < 72:
        errors.append(f"Pn offset {pn.offset} is smaller than the observed header")
    if pn.length == 0:
        errors.append("Pn length is zero")
    if aux.length == 0:
        errors.append(";n length is zero")
    if pn.end != aux.offset:
        errors.append(f"Pn end 0x{pn.end:X} != ;n offset 0x{aux.offset:X}")
    if aux.end != len(data):
        errors.append(f";n end 0x{aux.end:X} != file size 0x{len(data):X}")
    if pn.end > len(data) or aux.end > len(data):
        errors.append("a ZLD section extends beyond the end of the file")

    # Observed on R513A_no_FW.zld. Keep as validation, but not as the only
    # source of the section layout.
    if size_field + 20 != len(data):
        errors.append(
            f"size field 0x{size_field:X} + 20 != file size 0x{len(data):X}"
        )

    if errors:
        raise ValueError("invalid/unsupported ZLD:\n  " + "\n  ".join(errors))

    return ZLD(data, size_field, pn, aux)


def print_zld(path: Path, zld: ZLD) -> None:
    pn = zld.bytes_for(zld.pn)
    aux = zld.bytes_for(zld.aux)

    print("ZLD")
    print(f"File:             {path}")
    print(f"File size:        {len(zld.data)}")
    print(f"Header size:      {zld.pn.offset}")
    print(f"Size field:       0x{zld.size_field:X}")
    print()
    print("Pn / WPn")
    print(f"  type:           0x{zld.pn.type_id:X}")
    print(f"  offset:         {zld.pn.offset} (0x{zld.pn.offset:X})")
    print(f"  length:         {zld.pn.length} (0x{zld.pn.length:X})")
    print(f"  metadata:       0x{zld.pn.metadata:X}")
    print(f"  SHA256:         {sha256(pn)}")
    print()
    print(";n / W;n")
    print(f"  type:           0x{zld.aux.type_id:X}")
    print(f"  offset:         {zld.aux.offset} (0x{zld.aux.offset:X})")
    print(f"  length:         {zld.aux.length} (0x{zld.aux.length:X})")
    print(f"  metadata:       0x{zld.aux.metadata:X}")
    print(f"  SHA256:         {sha256(aux)}")
    print()
    print(
        f"Boundary:         {zld.pn.offset} + {zld.pn.length} "
        f"= {zld.aux.offset}"
    )
    print(
        f"End of file:      {zld.aux.offset} + {zld.aux.length} "
        f"= {len(zld.data)}"
    )


def bcc(start: int, body: bytes) -> int:
    value = start
    for byte in body:
        value ^= byte
    return value & 0xFF


def frame(body_text: str) -> bytes:
    body = body_text.encode("ascii")
    return (
        bytes([ENQ])
        + body
        + f"{bcc(ENQ, body):02X}".encode("ascii")
        + bytes([CR])
    )


def read_frame(ser: serial.Serial, timeout: float = REPLY_TIMEOUT) -> bytes:
    end = time.monotonic() + timeout
    data = bytearray()

    while time.monotonic() < end:
        byte = ser.read(1)
        if not byte:
            continue
        data += byte
        if byte[0] == CR:
            return bytes(data)

    raise TimeoutError("timed out waiting for PLC reply")


def decode(frame_data: bytes) -> tuple[int, str]:
    if len(frame_data) < 4 or frame_data[-1] != CR:
        raise RuntimeError(f"malformed PLC reply: {frame_data!r}")

    start = frame_data[0]
    text = frame_data[1:-1].decode("ascii", errors="replace")

    if len(text) < 2:
        raise RuntimeError(f"reply has no BCC: {frame_data!r}")

    body = text[:-2]

    try:
        got = int(text[-2:], 16)
    except ValueError as exc:
        raise RuntimeError(f"invalid reply BCC: {frame_data!r}") from exc

    calc = bcc(start, body.encode("ascii"))

    if got != calc:
        raise RuntimeError(f"BCC mismatch: got={got:02X} calc={calc:02X}")

    return start, body


def command(
    ser: serial.Serial,
    body: str,
    verbose: bool = False,
    timeout: float = REPLY_TIMEOUT,
) -> str:
    tx = frame(body)

    if verbose:
        print(f"TX:       {body}")
        print(f"TX(hex):  {tx.hex()}")

    ser.reset_input_buffer()
    ser.write(tx)
    ser.flush()

    raw = read_frame(ser, timeout)
    start, reply = decode(raw)

    if verbose:
        print(f"RX(hex):  {raw.hex()}")
        print(f"RX body:  {reply!r}")

    if start == NAK:
        raise RuntimeError(f"PLC NAK: {reply!r}")
    if start != ACK:
        raise RuntimeError(f"unexpected reply control byte 0x{start:02X}")

    # ACK command 2 = NG reply. Example: '01214'.
    if len(reply) >= 5 and reply[2] == "2":
        raise RuntimeError(f"PLC ACK/NG code={reply[3:5]} body={reply!r}")

    return reply


def parse_rs(text: str) -> dict:
    return {
        "raw": text,
        "state": text[0] if text else None,
        "protection": int(text[2]) if len(text) >= 3 and text[2] in "0123" else None,
        "crc": text[4:8] if len(text) >= 8 else None,
    }


def read_rs(plc: MiSmSerial, label: str) -> dict:
    rep = plc._xfer("0", "R", "S", b"")
    plc._raise_if_err(rep)

    rs = parse_rs(rep.data.decode("ascii", errors="replace"))
    states = {"0": "STOP", "1": "RUN / normal", "2": "USB-power-only"}

    print(f"{label} RS:           {rs['raw']!r}")
    print(f"{label} state:        {states.get(rs['state'], 'unknown')}")
    print(f"{label} protection:   {rs['protection']}")
    print(f"{label} program CRC:  {rs['crc']}")
    return rs


def read_rn(plc: MiSmSerial, label: str) -> str:
    rep = plc._xfer("0", "R", "N", b"")
    plc._raise_if_err(rep)

    text = rep.data.decode("ascii", errors="replace")
    print(f"{label} firmware/RN:  {text!r}")
    return text


def unlock(plc: MiSmSerial, password: str) -> None:
    try:
        raw = password.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError("legacy password must be ASCII") from exc

    if len(raw) > 8:
        raise ValueError("legacy password is limited to 8 characters")

    raw = raw.ljust(8, b"\x00")

    print("\nLegacy WV unlock...")
    rep = plc._xfer("0", "W", "V", raw + b"0")
    plc._raise_if_err(rep)
    print("Legacy WV accepted.")


def password_prompt(current: str | None, prompt: str = "PLC password: ") -> str:
    if current is not None:
        return current

    password = getpass.getpass(prompt)

    if not password:
        raise RuntimeError("password required")

    return password


def prepare(
    port: str,
    baud: int,
    password: str | None,
    verbose: bool,
) -> tuple[dict, str, str | None]:
    plc = MiSmSerial(
        port,
        device=DEVICE,
        baud=baud,
        debug=verbose,
        bcc_mode="auto",
    )

    try:
        print("\n--- PLC before download ---")
        rs = read_rs(plc, "Before")
        rn = read_rn(plc, "Before")

        if rs["protection"] != 0:
            password = password_prompt(password)
            unlock(plc, password)
            unlocked = read_rs(plc, "Unlocked")

            if unlocked["protection"] not in (None, 0):
                raise RuntimeError("PLC still reports protection enabled")

        print("\nStopping PLC...")
        plc.write_bit("M8000", 0)
        read_rs(plc, "Stop 1")

        # Retained from the successful WindLDR download sequence.
        plc.write_bit("M8000", 0)
        read_rs(plc, "Stop 2")

        return rs, rn, password

    finally:
        plc.close()


def ru_wait(ser: serial.Serial, verbose: bool) -> str:
    last = ""

    for attempt in range(1, RU_TRIES + 1):
        last = command(ser, RU, verbose)
        print(f"Ru[{attempt}]: {last!r}")

        if last.startswith("0101"):
            return last

        time.sleep(RU_DELAY)

    raise RuntimeError(f"Ru never became ready; last reply={last!r}")


def send_section(
    ser: serial.Serial,
    name: str,
    data: bytes,
    verbose: bool,
) -> None:
    declare = f"FF1{name}{BASE_ADDR}{len(data):04X}"
    rep = command(ser, declare, verbose)

    print(
        f"{name} declare: {len(data)} bytes "
        f"(0x{len(data):X}) -> {rep!r}"
    )

    blocks = [
        data[offset:offset + BLOCK_SIZE]
        for offset in range(0, len(data), BLOCK_SIZE)
    ]

    if not blocks:
        raise RuntimeError(f"{name} section is empty")

    for index, block in enumerate(blocks, 1):
        # Final/continuation is based on position, not block length.
        prefix = "FF0" if index == len(blocks) else "FF1"
        rep = command(ser, prefix + block.hex().upper(), verbose)

        print(
            f"{name} block {index}/{len(blocks)}: "
            f"{len(block)} bytes -> {rep!r}"
        )


def transfer(
    port: str,
    baud: int,
    pn: bytes,
    aux: bytes,
    verbose: bool,
) -> None:
    with serial.Serial(port, baud, timeout=SER_TIMEOUT) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print("\n--- Program transfer ---")

        rep = command(ser, RA, verbose)
        print(f"RA before WPn: {rep!r}")

        send_section(ser, "WPn", pn, verbose)

        print("\nWaiting for Pn processing...")
        ru_wait(ser, verbose)

        rep = command(ser, RA, verbose)
        print(f"RA before W;n: {rep!r}")

        send_section(ser, "W;n", aux, verbose)

        print("\nFinalizing...")
        ru_wait(ser, verbose)


def post_status(
    port: str,
    baud: int,
    verbose: bool,
) -> tuple[dict, str]:
    plc = MiSmSerial(
        port,
        device=DEVICE,
        baud=baud,
        debug=verbose,
        bcc_mode="auto",
    )

    try:
        print("\n--- PLC after download ---")
        return read_rs(plc, "After"), read_rn(plc, "After")
    finally:
        plc.close()


def unlock_for_verify(
    port: str,
    baud: int,
    password: str | None,
    verbose: bool,
) -> str | None:
    plc = MiSmSerial(
        port,
        device=DEVICE,
        baud=baud,
        debug=verbose,
        bcc_mode="auto",
    )

    try:
        rs = read_rs(plc, "Verify status")

        if rs["protection"] in (None, 0):
            return password

        print("\nDownloaded project is protected; unlocking for readback.")

        if password is not None:
            try:
                unlock(plc, password)
                return password
            except Exception:
                print("Previous password was not accepted by the downloaded project.")

        password = getpass.getpass("Downloaded project password: ")

        if not password:
            raise RuntimeError("readback requires the downloaded project password")

        unlock(plc, password)
        return password

    finally:
        plc.close()


def section_length(reply: str) -> int:
    match = re.search(r"n([0-9A-Fa-f]{8})$", reply)

    if not match:
        raise RuntimeError(f"could not parse resident section length: {reply!r}")

    return int(match.group(1), 16)


def data_reply(reply: str) -> bytes:
    if len(reply) < 3:
        raise RuntimeError(f"short data reply: {reply!r}")

    text = reply[3:]

    if len(text) % 2:
        raise RuntimeError(f"odd-length hex data reply: {reply!r}")

    try:
        return bytes.fromhex(text)
    except ValueError as exc:
        raise RuntimeError(f"non-hex data reply: {reply!r}") from exc


def read_section(
    ser: serial.Serial,
    name: str,
    verbose: bool,
) -> bytes:
    rep = command(ser, f"FF1{name}{BASE_ADDR}FFFF", verbose)
    length = section_length(rep)

    print(f"{name} resident length: {length} bytes (0x{length:X})")

    result = bytearray()

    while len(result) < length:
        remaining = length - len(result)
        request = "FF1R" if remaining > BLOCK_SIZE else "FF0R"
        block = data_reply(command(ser, request, verbose))

        if not block:
            raise RuntimeError(f"{name} returned an empty block")

        result.extend(block)

        print(
            f"{name} readback: {len(result)}/{length} bytes "
            f"(+{len(block)})"
        )

        if len(result) > length:
            raise RuntimeError(
                f"{name} returned too much data: {len(result)} > {length}"
            )

    return bytes(result)


def verify(
    port: str,
    baud: int,
    pn: bytes,
    aux: bytes,
    verbose: bool,
) -> bool:
    print("\n--- Resident program readback ---")

    with serial.Serial(port, baud, timeout=SER_TIMEOUT) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        resident_pn = read_section(ser, "RPn", verbose)
        resident_aux = read_section(ser, "R;n", verbose)

    pn_ok = resident_pn == pn
    aux_ok = resident_aux == aux

    print("\nReadback comparison")
    print(
        f"Pn length:          {'MATCH' if len(resident_pn) == len(pn) else 'MISMATCH'}"
        f"  source={len(pn)} resident={len(resident_pn)}"
    )
    print(f"Pn source SHA256:   {sha256(pn)}")
    print(f"Pn PLC SHA256:      {sha256(resident_pn)}")
    print(f"Pn bytes:           {'MATCH' if pn_ok else 'MISMATCH'}")
    print()
    print(
        f";n length:          "
        f"{'MATCH' if len(resident_aux) == len(aux) else 'MISMATCH'}"
        f"  source={len(aux)} resident={len(resident_aux)}"
    )
    print(f";n source SHA256:   {sha256(aux)}")
    print(f";n PLC SHA256:      {sha256(resident_aux)}")
    print(f";n bytes:           {'MATCH' if aux_ok else 'MISMATCH'}")

    if pn_ok and aux_ok:
        print(
            "\nRESULT: resident Pn and ;n are byte-for-byte identical "
            "to the ZLD sections."
        )
        return True

    print("\nRESULT: resident program does NOT match the ZLD sections.")
    return False


def restore_run(
    port: str,
    baud: int,
    was_running: bool,
    verbose: bool,
) -> None:
    if not was_running:
        return

    plc = MiSmSerial(
        port,
        device=DEVICE,
        baud=baud,
        debug=verbose,
        bcc_mode="auto",
    )

    try:
        rs = read_rs(plc, "Final")

        if rs["state"] != "1":
            print("\nRestoring RUN state...")
            plc.write_bit("M8000", 1)
            time.sleep(0.5)
            read_rs(plc, "Running")
    finally:
        plc.close()


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "FC6A ZLD downloader using ZLD section descriptors and "
            "legacy Compatibility-mode WV unlock."
        )
    )

    parser.add_argument("zld", type=Path)
    parser.add_argument("--port", default=PORT)
    parser.add_argument("--baud", type=int, default=BAUD)

    parser.add_argument(
        "--password",
        help="legacy PLC password; interactive prompt is safer",
    )

    parser.add_argument(
        "--inspect",
        action="store_true",
        help="parse the ZLD and exit without accessing the PLC",
    )

    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="skip RPn/R;n byte-for-byte verification",
    )

    parser.add_argument(
        "--no-run",
        action="store_true",
        help="do not restore RUN if the PLC was running before download",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="print complete TX/RX frames including program data",
    )

    return parser.parse_args()


def main() -> int:
    args = arguments()

    raw = args.zld.read_bytes()
    zld = parse_zld(raw)

    pn = zld.bytes_for(zld.pn)
    aux = zld.bytes_for(zld.aux)

    print_zld(args.zld, zld)

    if args.inspect:
        print("\nInspect only; no PLC commands were sent.")
        return 0

    print("\nTransfer")
    print(f"Port:             {args.port}")
    print(f"Baud:             {args.baud}")
    print(f"WPn bytes:        {len(pn)} (0x{len(pn):X})")
    print(f"W;n bytes:        {len(aux)} (0x{len(aux):X})")
    print("Firmware path:    not implemented")

    before, rn_before, password = prepare(
        args.port,
        args.baud,
        args.password,
        args.verbose,
    )

    transfer(args.port, args.baud, pn, aux, args.verbose)

    after, rn_after = post_status(args.port, args.baud, args.verbose)

    if rn_before == rn_after:
        print(f"RN unchanged:     {rn_after}")
    else:
        print(f"WARNING RN:       {rn_before!r} -> {rn_after!r}")

    verified = None

    if not args.no_verify:
        if after["protection"] not in (None, 0):
            password = unlock_for_verify(
                args.port,
                args.baud,
                password,
                args.verbose,
            )

        verified = verify(
            args.port,
            args.baud,
            pn,
            aux,
            args.verbose,
        )

    if not args.no_run:
        restore_run(
            args.port,
            args.baud,
            before["state"] == "1",
            args.verbose,
        )

    print("\nDownload complete.")

    if verified is False:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
