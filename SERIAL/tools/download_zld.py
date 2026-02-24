#!/usr/bin/env python3
"""
download_zld.py — download a .zld (user program) into IDEC FC6A PLC user space

This script is built from what we’ve proven *in this chat*:
- “Maintenance protocol” commands (stop PLC, read status) work reliably using MiSmSerial.py
- The actual program download (Ri / WPn / W;n + 736-byte chunks + Ru) follows the USB-capture dialect:
    TX: 0x05 + ASCII_BODY + BCC(2 hex) + 0x0D
    RX: 0x06/0x15 + ASCII_BODY + BCC(2 hex) + 0x0D
  where BCC = XOR(start_byte + body_ascii_bytes)

Safety:
- Stops PLC via M8000 = 0 (best-effort)
- Reads status via RS (best-effort)
- Then performs the download sequence

Usage:
  1) Put this file and MiSmSerial.py in the same directory
  2) chmod +x download_zld.py
  3) ./download_zld.py q1.zld

If you omit filename, it uses DEFAULT_ZLD_FILENAME.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Tuple, Optional
from time import sleep
import serial

# ---- must be present in same directory ----
from MiSmSerial import MiSmSerial  # type: ignore


# =============================================================================
# IMPORTANT VARIABLES (EDIT THESE)
# =============================================================================

# Serial/USB CDC
PORT = "/dev/ttyACM0"
BAUD = 9600

# ZLD
DEFAULT_ZLD_FILENAME = "q1.zld"
ZLD_OFFSET_BYTES = 72  # your known offset inside ZLD container

# Safety / maintenance checks
DO_SAFETY_STOP = True      # write M8000=0 (stop PLC)
DO_STATUS_RS = True        # read RS status

# Station / device
DEVICE = "FF"              # MiSmSerial device
CPU_TYPE = 0               # not used by capture-dialect, but kept for context

# Download dialect (capture-proven)
BASE_ADDR_HEX6 = "600000"  # seen in captures
CHUNK_SIZE_BYTES = 736     # 0x2E0 (safe to assume from captures)

SEG2_TAIL_LEN_BYTES = 340  # 0x0154 (observed tail segment size)
FORCE_SEG2_TAIL_SPLIT = True  # match capture behavior

# Prefixes (observed)
ST_CMD_SEG = "FF1"         # used for WPn / W;n
ST_DATA_FULL = "FF1"       # used for full data blocks
ST_DATA_TAIL = "FF0"       # used for tail/remainder blocks

# Ri/Ru (session control)
# You already tested this Ri and got ACK body "01083FF0000" — that is SUCCESS (it’s an ACK w/ data).
RI_STAGE1_BODIES: List[str] = [
    "FF0Ri00001FB800040",
]

# Optional additional Ri stage (leave empty if not needed)
RI_STAGE2_BODIES: List[str] = [
    # "FF0Ri..............",
]

# Ru: often repeated until “ready”; your capture analysis showed repeated Ru12.
RU_BODY = "FF0Ru12"
RU_MAX_TRIES = 8
RU_SLEEP_S = 1.0

# Timeouts
SER_READ_TIMEOUT_S = 0.05     # serial read timeout
REPLY_TIMEOUT_S = 3.0         # per command reply timeout

# Debug
PRINT_TX_RX = True
PRINT_BLOCK_PROGRESS_EVERY = 1  # print every block; set to e.g. 10 if you want less spam


# =============================================================================
# Download dialect framing helpers (USB-capture dialect)
# =============================================================================

ENQ = 0x05
ACK = 0x06
NAK = 0x15
CR  = 0x0D


def xor_bcc(start_byte: int, body_ascii: bytes) -> int:
    x = start_byte & 0xFF
    for b in body_ascii:
        x ^= b
    return x & 0xFF


def encode_frame(body_text: str) -> bytes:
    body = body_text.encode("ascii")
    bcc = xor_bcc(ENQ, body)
    return bytes([ENQ]) + body + f"{bcc:02X}".encode("ascii") + bytes([CR])


def read_until_cr(ser: serial.Serial, timeout_s: float) -> bytes:
    end = time.monotonic() + timeout_s
    buf = bytearray()
    while time.monotonic() < end:
        b = ser.read(1)
        if b:
            buf += b
            if b[0] == CR:
                return bytes(buf)
    raise TimeoutError("Timed out waiting for CR-terminated reply")


def decode_reply(frame: bytes) -> Tuple[int, str]:
    """
    Expected reply:
      start(ACK/NAK) + ASCII(body) + BCC(2 hex) + CR
    with BCC = XOR(start + body_bytes)
    """
    if not frame or frame[-1] != CR or len(frame) < 1 + 2 + 1:
        raise RuntimeError(f"Malformed reply: {frame!r}")

    start = frame[0]
    txt = frame[1:-1].decode("ascii", errors="replace")
    if len(txt) < 2:
        raise RuntimeError(f"Reply missing BCC: {frame!r}")

    body = txt[:-2]
    got = int(txt[-2:], 16)
    calc = xor_bcc(start, body.encode("ascii"))
    if got != calc:
        raise RuntimeError(f"Reply BCC mismatch got={got:02X} calc={calc:02X} frame={frame!r}")

    return start, body


def ack_success(body: str) -> bool:
    """
    We treat ANY ACK body starting with "01" as success.
    Examples you’ve seen:
      - "01037"           (CTS / OK)
      - "01083FF0000"     (Ri response with data)
    """
    return body.startswith("01")


def send_cmd(ser: serial.Serial, body: str, *, timeout_s: float = REPLY_TIMEOUT_S) -> str:
    frame = encode_frame(body)
    if PRINT_TX_RX:
        print(f"TX: {body}  raw={frame!r}")

    # clear any stale bytes just before sending
    ser.reset_input_buffer()

    ser.write(frame)
    ser.flush()

    raw = read_until_cr(ser, timeout_s)
    start, rep_body = decode_reply(raw)

    if PRINT_TX_RX:
        print(f"RX: raw={raw!r} start=0x{start:02X} body={rep_body!r}")

    if start == NAK:
        raise RuntimeError(f"PLC NAK: body={rep_body!r} raw={raw!r}")
    if start != ACK:
        raise RuntimeError(f"Unexpected reply start=0x{start:02X} body={rep_body!r} raw={raw!r}")
    if not ack_success(rep_body):
        raise RuntimeError(f"ACK but unexpected body={rep_body!r} raw={raw!r}")

    return rep_body


def chunks(data: bytes, n: int) -> List[bytes]:
    return [data[i:i+n] for i in range(0, len(data), n)]


# =============================================================================
# Maintenance “safety” helpers (MiSmSerial)
# =============================================================================

def safety_stop_and_status() -> None:
    plc = MiSmSerial(
        PORT,
        device=DEVICE,
        baud=BAUD,
        debug=True,
        bcc_mode="auto",   # important: MiSmSerial will lock correct request BCC mode
    )
    try:
        if DO_SAFETY_STOP:
            print("\n[SAFETY] Stop PLC: write_bit(M8000, 0)")
            plc.write_bit("M8000", 0)

        if DO_STATUS_RS:
            print("\n[SAFETY] RS status")
            rep = plc._xfer("0", "R", "S", b"")  # type: ignore
            plc._raise_if_err(rep)              # type: ignore
            # Print raw; interpretation can be refined later
            print(f"[SAFETY] RS reply: command={rep.command!r} data={rep.data!r} hex={rep.data.hex()}")

        print(f"[SAFETY] MiSmSerial locked request BCC mode: {plc.bcc_mode!r}")

    finally:
        plc.close()


# =============================================================================
# Download procedure
# =============================================================================

def download_zld_bytes(program: bytes) -> None:
    with serial.Serial(PORT, BAUD, timeout=SER_READ_TIMEOUT_S) as ser:
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        print("\n[DL] Ri stage 1")
        for i, body in enumerate(RI_STAGE1_BODIES, 1):
            rep = send_cmd(ser, body)
            print(f"[DL] Ri1[{i}] -> {rep!r}")

        # split seg1/seg2 like captures
        if FORCE_SEG2_TAIL_SPLIT and len(program) > SEG2_TAIL_LEN_BYTES:
            seg1 = program[:-SEG2_TAIL_LEN_BYTES]
            seg2 = program[-SEG2_TAIL_LEN_BYTES:]
        else:
            seg1 = program
            seg2 = b""

        print(f"\n[DL] program bytes={len(program)} seg1={len(seg1)} seg2={len(seg2)}")
        if seg2 and len(seg2) != SEG2_TAIL_LEN_BYTES:
            print(f"[DL] NOTE: seg2 len is {len(seg2)} (expected {SEG2_TAIL_LEN_BYTES} if capture-matching)")

        print("\n[DL] WPn declare seg1 length")
        wp = f"{ST_CMD_SEG}WPn{BASE_ADDR_HEX6}{len(seg1):04X}"
        rep = send_cmd(ser, wp)
        print(f"[DL] WPn -> {rep!r}")

        # send seg1 blocks
        blocks = chunks(seg1, CHUNK_SIZE_BYTES)
        print(f"\n[DL] Sending seg1 blocks: {len(blocks)} blocks @ {CHUNK_SIZE_BYTES} bytes each (last may be shorter)")
        for idx, blk in enumerate(blocks, 1):
            station = ST_DATA_FULL if len(blk) == CHUNK_SIZE_BYTES else ST_DATA_TAIL
            body = station + blk.hex().upper()
            rep = send_cmd(ser, body)

            if (idx % PRINT_BLOCK_PROGRESS_EVERY) == 0:
                print(f"[DL] seg1 block {idx}/{len(blocks)} bytes={len(blk)} station={station} -> {rep!r}")

        # Ru “ready/busy” loop
        print("\n[DL] Ru loop (wait for ready)")
        last = None
        for attempt in range(1, RU_MAX_TRIES + 1):
            last = send_cmd(ser, RU_BODY)
            print(f"[DL] Ru[{attempt}] -> {last!r}")
            # If it reports ready, usually it changes to a different 0101... body.
            # We accept any 01... already; this loop mainly gives PLC breathing room if it’s busy.
            if last.startswith("0101"):
                break
            time.sleep(RU_SLEEP_S)

        # optional Ri stage2
        if RI_STAGE2_BODIES:
            print("\n[DL] Ri stage 2")
            for i, body in enumerate(RI_STAGE2_BODIES, 1):
                rep = send_cmd(ser, body)
                print(f"[DL] Ri2[{i}] -> {rep!r}")

        # seg2 if present
        if seg2:
            print("\n[DL] W;n declare seg2 length")
            wn = f"{ST_CMD_SEG}W;n{BASE_ADDR_HEX6}{len(seg2):04X}"
            rep = send_cmd(ser, wn)
            print(f"[DL] W;n -> {rep!r}")

            print("\n[DL] Send seg2 data")
            body2 = ST_DATA_TAIL + seg2.hex().upper()
            rep = send_cmd(ser, body2)
            print(f"[DL] seg2 data -> {rep!r}")

        # final Ru
        print("\n[DL] Final Ru")
        rep = send_cmd(ser, RU_BODY)
        print(f"[DL] Final Ru -> {rep!r}")

        print("\n[DL] DONE (script completed without NAK/timeout)")

def runProg():
    PORT = "/dev/ttyACM0"
    plc = MiSmSerial(PORT, device="FF", baud=9600, debug=True, bcc_mode="auto",)
    plc.write_bit("M8000", 1) # tell the PLC to run
    plc.close()

def main() -> int:
    zld_path = Path(sys.argv[1]) if len(sys.argv) >= 2 else Path(DEFAULT_ZLD_FILENAME)
    zld = zld_path.read_bytes()
    if len(zld) < ZLD_OFFSET_BYTES:
        raise RuntimeError(f"ZLD too short: {len(zld)} < offset {ZLD_OFFSET_BYTES}")

    program = zld[ZLD_OFFSET_BYTES:]

    print(f"ZLD file: {zld_path}")
    print(f"ZLD length: {len(zld)}")
    print(f"Offset: {ZLD_OFFSET_BYTES} -> program bytes: {len(program)}")
    print(f"Port: {PORT} @ {BAUD}")
    print(f"Device: {DEVICE}  CPU type: {CPU_TYPE}")

    # Safety checks using proven maintenance library
    safety_stop_and_status()

    # Download using capture dialect
    download_zld_bytes(program)
    sleep(1) # 500ms? 3s? something
    runProg() 
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
