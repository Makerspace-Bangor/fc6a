#!/usr/bin/env python3
from MiSmSerial import MiSmSerial
"""
This program operates on the serial port, to tell you how the 
Ethernet ports are configured.
"""
PORT = "/dev/ttyACM0" # change to your serial port


def read_regs(plc, start, count):
    return [
        plc.read(f"D{start + i:04d}")
        for i in range(count)
    ]


def ip(plc, start):
    return ".".join(str(v) for v in read_regs(plc, start, 4))


def mac(plc, start):
    return ":".join(f"{v & 0xFF:02X}" for v in read_regs(plc, start, 6))


plc = MiSmSerial(
    PORT,
    device="FF",
    timeout=2.0,
    debug=False,
)

print("Network config")
print()
print("Ethernet Port 1")
print(f"  MAC:     {mac(plc, 8324)}")
print(f"  IP:      {ip(plc, 8330)}")
print(f"  Mask:    {ip(plc, 8334)}")
print(f"  Gateway: {ip(plc, 8338)}")

print()

print("Ethernet Port 2")
print(f"  MAC:     {mac(plc, 8651)}")
print(f"  IP:      {ip(plc, 8657)}")
print(f"  Mask:    {ip(plc, 8661)}")
print(f"  Gateway: {ip(plc, 8665)}")

plc.close()
