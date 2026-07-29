#!/usr/bin/env python3
"""
check_protection_serial.py

Reads PLC Operating Status (RS34) over SERIAL using MiSmSerial.py
and prints:
- Run/Stop
- User program protection mode
- CPU module type code

Usage:
  python3 check_protection_serial.py --port /dev/ttyACM0 --device FF --debug
"""

from __future__ import annotations

import argparse
from MiSmSerial import MiSmSerial


PROTECT_MAP = {
    "0": "Not protected",
    "1": "Write protect",
    "2": "Read protect",
    "3": "Read + write protect",
}

RUNSTOP_MAP = {
    "0": "Run",
    "1": "Stop",
}

CPU_MAP = {
    "0": "10-I/O",
    "1": "16-I/O",
    "2": "20-I/O transistor output",
    "3": "24-I/O",
    "4": "40-I/O",
    "6": "20-I/O relay output",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True, help="Serial port (e.g. /dev/ttyACM0)")
    ap.add_argument("--device", default="FF", help="Device (2 ASCII hex chars), default FF")
    ap.add_argument("--baud", type=int, default=19200)
    ap.add_argument("--timeout", type=float, default=1.0)
    ap.add_argument("--bcc-mode", default="auto", choices=["auto", "enq", "no_enq"])
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    plc = MiSmSerial(
        args.port,
        device=args.device.upper(),
        baud=args.baud,
        timeout=args.timeout,
        debug=args.debug,
        bcc_mode=args.bcc_mode,
    )

    try:
        # RS34: Read PLC operating status
        rep = plc._xfer("0", "R", "S", b"34")
        plc._raise_if_err(rep)

        # rep.data is the reply "data" field (everything after cmd byte and before BCC)
        # It is ASCII bytes. The doc says key fields are 1 byte each:
        #   [0] PLC operating status: '0' run, '1' stop
        #   [1] timer/counter preset value change: '0' not changed, '1' changed
        #   [2] user program protection: '0'..'3'
        #   [3] CPU module type code: '0','1','2','3','4','6'
        data = rep.data.decode("ascii", errors="replace")

        if len(data) < 4:
            print(f"Unexpected RS34 reply length: {len(data)} data={data!r}")
            print(f"Raw data hex: {rep.data.hex()}")
            return 2

        runstop = data[0]
        changed = data[1]
        protect = data[2]
        cpu = data[3]

        print("RS34 decoded:")
        print(f"  PLC status:            {RUNSTOP_MAP.get(runstop, 'Unknown')} ({runstop!r})")
        print(f"  Preset value changed:  {'Changed' if changed == '1' else 'Not changed'} ({changed!r})")
        print(f"  User prog protection:  {PROTECT_MAP.get(protect, 'Unknown')} ({protect!r})")
        print(f"  CPU type code:         {CPU_MAP.get(cpu, 'Unknown')} ({cpu!r})")

        # Show extra bytes if present (CRC + sumcheck often follow)
        if len(data) > 4:
            print(f"  Extra bytes (len={len(data)-4}): {data[4:]}")

        return 0

    finally:
        plc.close()


if __name__ == "__main__":
    raise SystemExit(main())
