#!/usr/bin/env python3
"""
MiSmSDCard - FC6A PLC SD Card helper for MiSmTCP / MiSmSerial style objects.

This module does not own the connection. It borrows an existing PLC object and
uses either:
  - plc.sd_xfer(packet) / plc._sd_xfer(packet), if you add one later
  - plc._ser for serial objects like MiSmSerial
  - plc._send(packet) for TCP objects like FC6AMaint / MiSmTCP-style classes

Intended use:
    from MiSmSDCard import MiSmSDCard
    from MiSmTCP import MiSmTCP
    plc = MiSmTCP("192.168.1.50")
    plc.SD = MiSmSDCard(plc)

    print(plc.SD.checkSD())
    print(plc.SD.listSD("/FCDATA01/DATALOG/1-secLog"))
    plc.SD.deleteSD("/cap")

Implemented operations:
    checkSD()      register checks + optional extended SD status poll
    listSD(path)   directory listing based on observed DataFileManager frames    
    walkSD(...)    Recursively list SD card entries below path.

Not yet implemented:
    deleteSD(...)   delete path or file
    readSD(...)     print contents of a file
    writeSD(...)    write files to plc SD card path
    saveSD(...)     like read, but save output
    
MiSmTCP fails about half the time. Not sure why assume timing.    
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Union
import re
import socket
import time


# -------------------------
# Low-level helpers
# -------------------------


def _xor_bcc(data: bytes) -> int:
    x = 0
    for b in data:
        x ^= b
    return x & 0xFF


def _bcc_ascii(data: bytes) -> bytes:
    return f"{_xor_bcc(data):02X}".encode("ascii")


def _frame_bcc(body: bytes) -> bytes:
    """Frame with ENQ, XOR BCC including ENQ, and CR."""
    msg = b"\x05" + body
    return msg + _bcc_ascii(msg) + b"\r"


def _frame_no_bcc(body: bytes) -> bytes:
    """Frame with ENQ and CR only. Some SD entry-read frames use this."""
    return b"\x05" + body + b"\r"


def _printable(data: bytes) -> str:
    out = []
    for b in data:
        if 32 <= b <= 126:
            out.append(chr(b))
        elif b == 0x00:
            out.append("<NUL>")
        elif b == 0x05:
            out.append("<ENQ>")
        elif b == 0x06:
            out.append("<ACK>")
        elif b == 0x15:
            out.append("<NAK>")
        elif b == 0x0D:
            out.append("<CR>")
        else:
            out.append(f"<{b:02X}>")
    return "".join(out)


def _norm_path(path: Optional[str] = "/") -> str:
    if path is None or path == "":
        return "/"
    return "/" + str(path).strip("/")


def _join_path(path: str, file: Optional[str] = None) -> str:
    path = _norm_path(path)
    if not file:
        return path
    return path.rstrip("/") + "/" + str(file).strip("/")


def _body_open_dir(device: str, path: str) -> bytes:
    path = _norm_path(path)
    path_bytes = path.encode("ascii") + b"\x00"
    return device.encode("ascii") + b"1FR" + f"{len(path_bytes):03X}".encode("ascii") + path_bytes


def _body_resolve_path(device: str, path: str) -> bytes:
    # Observed notes show: FF1FR005/path
    # This is not the same path-length format as directory open.
    return device.encode("ascii") + b"1FR005" + _norm_path(path).encode("ascii")


def _body_delete_path(device: str, path: str) -> bytes:
    # Observed notes show: FF0FC005/path
    return device.encode("ascii") + b"0FC005" + _norm_path(path).encode("ascii")


@dataclass
class SDReply:
    kind: str
    raw: bytes
    device: str = ""
    command: str = ""
    data: bytes = b""
    bcc_recv: Optional[int] = None
    bcc_calc: Optional[int] = None
    bcc_ok: bool = False
    ng_code: str = ""
    nak_code: str = ""

    @property
    def ok(self) -> bool:
        return self.kind == "ACK_OK" and self.bcc_ok


def _parse_reply(raw: bytes) -> SDReply:
    if not raw:
        return SDReply(kind="EMPTY", raw=raw)
    if raw[-1:] != b"\r" or len(raw) < 6:
        return SDReply(kind="MALFORMED", raw=raw)

    ctrl = raw[0:1]
    dev = raw[1:3]
    cmd = raw[3:4]
    data = raw[4:-3]
    bcc_ascii = raw[-3:-1]

    try:
        bcc_recv = int(bcc_ascii.decode("ascii"), 16)
    except Exception:
        return SDReply(kind="MALFORMED", raw=raw)

    bcc_calc = _xor_bcc(raw[0:-3])
    bcc_ok = bcc_recv == bcc_calc

    rep = SDReply(
        kind="UNKNOWN",
        raw=raw,
        device=dev.decode("ascii", errors="replace"),
        command=cmd.decode("ascii", errors="replace"),
        data=data,
        bcc_recv=bcc_recv,
        bcc_calc=bcc_calc,
        bcc_ok=bcc_ok,
    )

    if ctrl == b"\x15":
        rep.kind = "NAK"
        rep.nak_code = data[:2].decode("ascii", errors="replace") if len(data) >= 2 else ""
        return rep

    if ctrl == b"\x06":
        if rep.command == "2":
            rep.kind = "ACK_NG"
            rep.ng_code = data[:2].decode("ascii", errors="replace") if len(data) >= 2 else ""
            return rep
        rep.kind = "ACK_OK"
        return rep

    return rep


def _parse_entry(payload: bytes) -> Optional[Dict[str, Any]]:
    payload = payload.rstrip(b"\x00")

    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError:
        return None

    m = re.match(
        r"^([01])([0-9A-Fa-f]{8})([0-9]{8})([0-9]{6})([0-9A-Fa-f]{3})(.*)$",
        text,
    )
    if not m:
        return None

    kind, size_hex, date, tm, name_len_hex, name = m.groups()
    name_len = int(name_len_hex, 16)
    name = name[:name_len]

    return {
        "is_dir": kind == "1",
        "size": int(size_hex, 16),
        "date": date,
        "time": tm,
        "name": name,
        "raw": text,
    }


# -------------------------
# SD Card feature object
# -------------------------


class MiSmSDCard:
    def __init__(self, plc: Any, device: Optional[str] = None, timeout: float = 2.0, debug: Optional[bool] = None):
        self.plc = plc
        self.device = (device or self._guess_device()).upper()
        self.timeout = timeout
        self.debug = bool(getattr(plc, "debug", False) if debug is None else debug)

    # ----------
    # Public API
    # ----------

    def checkSD(self, extended: bool = True) -> Dict[str, Any]:
        """
        Quick SD status check.

        Uses standard PLC devices first:
          M8070 = SD mounted/recognized
          M8071 = accessing SD card
          D8005 bit 12 = SD memory card transfer error
          D8005 bit 14 = SD memory card access error

        If extended=True, also sends observed SD status poll:
          FF0RA1F5F0220
        """
        mounted = self._safe_read_bit("M8070")
        accessing = self._safe_read_bit("M8071")
        d8005 = self._safe_read_word("D8005")

        transfer_error = bool(d8005 & (1 << 12)) if d8005 is not None else None
        access_error = bool(d8005 & (1 << 14)) if d8005 is not None else None

        out: Dict[str, Any] = {
            "mounted": mounted,
            "accessing": accessing,
            "D8005": d8005,
            "transfer_error": transfer_error,
            "access_error": access_error,
            "ok": bool(mounted) and not bool(transfer_error) and not bool(access_error),
        }

        if extended:
            try:
                rep = self._request(_frame_bcc(self.device.encode("ascii") + b"0RA1F5F0220"), "sd status")
                out["extended_raw"] = rep.data.decode("ascii", errors="replace")
                out["extended_reply_ok"] = rep.ok
            except Exception as e:
                out["extended_error"] = str(e)

        return out

    def listSD(self, path: str = "/") -> List[Dict[str, Any]]:
        """List files/folders at a PLC SD card path."""
        path = _norm_path(path)

        open_rep = self._request(_frame_bcc(_body_open_dir(self.device, path)), f"open dir {path}")
        self._raise_if_bad(open_rep)

        try:
            count = int(open_rep.data.decode("ascii"), 16)
        except Exception as e:
            raise IOError(f"Could not decode directory count from {open_rep.data!r}") from e

        entries: List[Dict[str, Any]] = []
        for i in range(count):
            body = self.device.encode("ascii") + (b"0FR21" if i == count - 1 else b"1FR20")
            rep = self._request(_frame_no_bcc(body), f"entry {i + 1}/{count}")
            self._raise_if_bad(rep)

            entry = _parse_entry(rep.data)
            if entry is None:
                raise IOError(f"Could not parse directory entry {i + 1}/{count}: {_printable(rep.data)}")

            entry["path"] = path
            entries.append(entry)
            time.sleep(0.02)

        return entries

    def walkSD(self, path: str = "/") -> List[Dict[str, Any]]:
        """Recursively list SD card entries below path."""
        path = _norm_path(path)
        found: List[Dict[str, Any]] = []

        for entry in self.listSD(path):
            full_path = _join_path(path, entry["name"])
            entry = dict(entry)
            entry["full_path"] = full_path
            found.append(entry)
            print(full_path)
            if entry.get("is_dir"):
                found.extend(self.walkSD(full_path))

        return found

    def deleteSD(self, path: str, file: Optional[str] = None) -> bool:
        """
        Delete a file or folder from the PLC SD card.

        Examples:
            plc.SD.deleteSD("/cap")
            plc.SD.deleteSD("/FCDATA01/DATALOG", "LOG_260625.CSV")
        """
        target = _join_path(path, file)

        # Captures/notes show DataFileManager resolves path twice before delete.
	# not sure we need to do that. 
        for _ in range(2):
            rep = self._request(_frame_bcc(_body_resolve_path(self.device, target)), f"resolve {target}")
            self._raise_if_bad(rep)

        rep = self._request(_frame_bcc(_body_delete_path(self.device, target)), f"delete {target}")
        self._raise_if_bad(rep)
        return True

    def readSD(self, path: str, file: Optional[str] = None) -> bytes:
        target = _join_path(path, file)
        raise NotImplementedError(f"readSD({target!r}) is not implemented yet.")

    def writeSD(self, path: str, file: Optional[str] = None, data: Union[str, bytes, None] = None) -> None:
        target = _join_path(path, file)
        raise NotImplementedError(f"writeSD({target!r}) is not implemented yet; write-file protocol is still unknown.")

    def saveSD(self, path: Optional[str] = None, file: Optional[str] = None) -> None:
        target = _join_path(path or "/", file)
        raise NotImplementedError(f"saveSD({target!r}) is not implemented yet.")

    # ----------
    # Internals
    # ----------

    def _guess_device(self) -> str:
        dev = getattr(self.plc, "device", "FF")
        if isinstance(dev, bytes):
            return dev.decode("ascii", errors="replace")
        return str(dev)

    def _request(self, packet: bytes, label: str = "") -> SDReply:
        if self.debug:
            print()
            print("TX", label)
            print("TX hex:", packet.hex(" ").upper())
            print("TX txt:", _printable(packet))

        raw = self._raw_xfer(packet)

        if self.debug:
            print("RX hex:", raw.hex(" ").upper() if raw else "")
            print("RX txt:", _printable(raw) if raw else "")

        rep = _parse_reply(raw)

        if self.debug:
            print("DATA  :", _printable(rep.data))

        return rep

    def _raw_xfer(self, packet: bytes) -> bytes:
        """Send one already-framed packet through the parent PLC object's transport."""
        # Preferred explicit hooks, if you add one to MiSmTCP/MiSmSerial later.
        for name in ("sd_xfer", "_sd_xfer", "raw_xfer", "_raw_xfer"):
            fn = getattr(self.plc, name, None)
            if callable(fn):
                return fn(packet)

        # MiSmSerial-style object.
        ser = getattr(self.plc, "_ser", None)
        if ser is not None:
            try:
                ser.reset_input_buffer()
            except Exception:
                pass
            ser.write(packet)
            ser.flush()
            return self._serial_recv_until_cr(ser)

        # FC6AMaint / simple MiSmTCP-style object.
        send = getattr(self.plc, "_send", None)
        if callable(send):
            return send(packet)

        # Fallback for objects with ip/host and port attributes but no _send().
        host = getattr(self.plc, "host", None) or getattr(self.plc, "ip", None)
        port = int(getattr(self.plc, "port", 2101))
        timeout = float(getattr(self.plc, "timeout", self.timeout))
        if host:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                sock.sendall(packet)
                return self._socket_recv_until_cr(sock)

        raise TypeError("PLC object has no supported raw transport (_ser, _send, host/ip, or raw_xfer).")

    def _serial_recv_until_cr(self, ser: Any, limit: int = 8192) -> bytes:
        end = time.time() + self.timeout
        buf = bytearray()
        while time.time() < end and len(buf) < limit:
            b = ser.read(1)
            if not b:
                continue
            buf.extend(b)
            if b == b"\r":
                break
        return bytes(buf)

    def _socket_recv_until_cr(self, sock: socket.socket, limit: int = 8192) -> bytes:
        buf = bytearray()
        while len(buf) < limit:
            chunk = sock.recv(256)
            if not chunk:
                break
            buf.extend(chunk)
            if b"\r" in chunk:
                break
        if b"\r" in buf:
            buf = buf.split(b"\r", 1)[0] + b"\r"
        return bytes(buf)

    def _raise_if_bad(self, rep: SDReply) -> None:
        if rep.kind == "NAK":
            raise IOError(f"PLC replied NAK code={rep.nak_code} raw={rep.raw.hex()}")
        if rep.kind == "ACK_NG":
            raise IOError(f"PLC replied ACK/NG code={rep.ng_code} raw={rep.raw.hex()}")
        if rep.kind != "ACK_OK":
            raise IOError(f"Unexpected reply kind={rep.kind} raw={rep.raw.hex()}")
        if not rep.bcc_ok:
            raise IOError(
                f"Reply BCC mismatch: recv={rep.bcc_recv:02X} calc={rep.bcc_calc:02X} raw={rep.raw.hex()}"
            )

    def _safe_read_bit(self, addr: str) -> Optional[int]:
        # Preferred modern MiSmSerial style: read_bit("M8070")
        fn = getattr(self.plc, "read_bit", None)
        if callable(fn):
            try:
                return int(fn(addr))
            except TypeError:
                pass
            except Exception:
                return None

        # Older/simple style: read_bits(8070)
        fn = getattr(self.plc, "read_bits", None)
        if callable(fn):
            try:
                num = int(re.sub(r"\D", "", addr))
                return int(bool(fn(num)))
            except Exception:
                return None

        return None

    def _safe_read_word(self, addr: str) -> Optional[int]:
        # Preferred modern MiSmSerial style: read("D8005")
        fn = getattr(self.plc, "read", None)
        if callable(fn):
            try:
                return int(fn(addr))
            except TypeError:
                pass
            except Exception:
                return None

        # Older/simple style: read_word(8005)
        fn = getattr(self.plc, "read_word", None)
        if callable(fn):
            try:
                num = int(re.sub(r"\D", "", addr))
                return int(fn(num))
            except Exception:
                return None

        return None
