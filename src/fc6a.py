#!/usr/bin/env python3
import socket
import struct
import time

### WARNING!!! ###
'''
This library will let you do some things that the IDEC PLC might never do. Such as:
Write or Read a float from an even register to an odd one. 
in the IDEC Conventions, registers as floats are odd then even.

This may be configurable in the settings, though Its not default.

Here, we assume the data type is whatever function call you provide, and that the upper byte is the 
next consecutive register. .. so be cautius, that you are reading and writing the correct registers
else extraneous reults may occur.

TODO: FIX Write bit
TODO: Force bits?
TODO: Add doubles

Limited datatypes supported at this time. B,F,W

'''

PLC_PORT = 2101 # change if needed
TIMEOUT = 1.0

def _bcc(data: bytes) -> bytes:
    """Calculate XOR-based Block Check Character."""
    bcc = 0
    for b in data:
        bcc ^= b
    return f"{bcc:02X}".encode("ascii")

def _frame(msg: bytes) -> bytes:
    """Append BCC and CR terminator to message."""
    return msg + _bcc(msg) + b"\r"

class FC6AMaint:
    def __init__(self, ip: str, device="FF"):
        self.ip = ip
        self.device = device.encode("ascii")

    # --- Low-level I/O ---
    def _send(self, payload: bytes) -> bytes:
        """Send command and receive response."""
        with socket.create_connection((self.ip, PLC_PORT), timeout=TIMEOUT) as s:
            s.sendall(payload)
            data = s.recv(1024)
            return data

    # --- Message builders ---
    def _build_read(self, dtype: str, addr: int, nbytes: int) -> bytes:
        msg = b"\x05" + self.device + b"0R" + dtype.encode("ascii") + f"{addr:04d}{nbytes:02X}".encode("ascii")
        return _frame(msg)

    def _build_write(self, dtype: str, addr: int, data_hex: str) -> bytes:
        nbytes = len(data_hex) // 2
        msg = b"\x05" + self.device + b"0W" + dtype.encode("ascii") + f"{addr:04d}{nbytes:02X}".encode("ascii") + data_hex.encode("ascii")
        return _frame(msg)

    # --- High-level accessors ---
    def read_bits(self, addr: int, count: int = 1):
        """Read bit(s) from M relays."""
        req = self._build_read("M", addr, count)
        resp = self._send(req)
        if not resp or resp[0] != 0x06:
            raise IOError(f"Bad response: {resp!r}")
        bitval = chr(resp[4])
        return bitval == "1"

    def write_bit(self, addr: int, value: bool):
        """Write one bit (on/off) to M relay."""
        cmd = b"\x05" + self.device + b"0Wm" + f"{addr:04d}".encode("ascii") + (b"1" if value else b"0")
        req = _frame(cmd)
        resp = self._send(req)
        if resp[:1] != b"\x06":
            raise IOError(f"Write bit failed: {resp!r}")

    def read_word(self, addr: int):
        """Read a 16-bit word (D register)."""
        req = self._build_read("D", addr, 2)
        resp = self._send(req)
        if resp[0] != 0x06:
            raise IOError(f"Bad response: {resp!r}")
        data_hex = resp[4:-3].decode("ascii")
        return int(data_hex, 16)

    def write_word(self, addr: int, value: int):
        """Write a 16-bit word (D register)."""
        hex_str = f"{value:04X}"
        req = self._build_write("D", addr, hex_str)
        resp = self._send(req)
        if resp[0] != 0x06:
            raise IOError(f"Write failed: {resp!r}")

    def read_float(self, addr: int, swapped=True):
        """Read 32-bit float (2 words)."""
        req = self._build_read("D", addr, 4)
        resp = self._send(req)
        if resp[0] != 0x06:
            raise IOError(f"Bad response: {resp!r}")
        hex_str = resp[4:-3].decode("ascii")
        lo = int(hex_str[0:4], 16)
        hi = int(hex_str[4:8], 16)
        val = (lo << 16 | hi) if swapped else (hi << 16 | lo)
        return struct.unpack(">f", struct.pack(">I", val))[0]

    def write_float(self, addr: int, value: float, swapped=True):
        """Write 32-bit float (2 words)."""
        raw = struct.unpack(">I", struct.pack(">f", value))[0]
        hi, lo = (raw >> 16) & 0xFFFF, raw & 0xFFFF
        if swapped:
            hi, lo = lo, hi
        data = f"{hi:04X}{lo:04X}"
        req = self._build_write("D", addr, data)
        resp = self._send(req)
        if resp[0] != 0x06:
            raise IOError(f"Write float failed: {resp!r}")
