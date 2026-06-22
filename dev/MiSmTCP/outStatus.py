#!/usr/bin/env python3
import time
from MiSmTCP import MiSmTCP
# Report output statuses
"""
Maintenance Protocol refers to what you know as I,Q
as X (inputs), Y (outputs)

Can we write an input?
Lol no, well, maybe but I havent figured it out.
"""


# Read Output Statuses
PLC_IP = "192.168.1.50"
plc = MiSmTCP(PLC_IP, debug=False)

for i in range(8):
    stat = plc.read_bit(f"Y000{i}")
    print(f"Output{i}: stat:{stat}")
    time.sleep(0.15)
print()
for i in range(8):
    stat = plc.read_bit(f"Q000{i}")
    print(f"Output{i}: stat:{stat}")
    time.sleep(0.15)

print()
# Read Input statuses
for i in range(8):
    stat = plc.read_bit(f"X000{i}")
    print(f"Input {i}: {stat}")
print()
# Read Input statuses
for i in range(8):
    stat = plc.read_bit(f"I000{i}")
    print(f"Input {i}: {stat}")
