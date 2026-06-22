#!/usr/bin/env python3

import time
from MiSmTCP import MiSmTCP
"""
Basic functionality Check
"""

PLC_IP = "192.168.1.50"
OUTPUT_COUNT = 8

mism.PRECISION = 4

#plc = MiSmTCP(PLC_IP, debug=True)
plc = MiSmTCP(PLC_IP, debug=False)

try:
    print(f"Connected to {PLC_IP}")

    print("\nCascading outputs...")
    for q in range(OUTPUT_COUNT):
        print(f"Q{q} ON")
        plc.output(q, 1)
        time.sleep(0.15)

        print(f"Q{q} OFF")
        plc.output(q, 0)
        time.sleep(0.05)

    print("\nReading D0100...")
    print("D0100 =", plc.read("D0100"))

    print("\nSetting timers T0420 and T0421...")
    for t in (420, 421):
        plc.write_timer(t, value=99999, preset=1000)
        print(f"T{t:04d} =", plc.read_timer(t)[0])

    print("\nReading D0040 as float...")
    print("Endian 0 =", plc.read_float("D0040", endian=0))
    print("Endian 1 =", plc.read_float("D0040", endian=1))

    print("\nReading D8056...")
    print("D8056 =", plc.read("D8056"))

    print("\nReading D8029 Firmware Version Word...")
    print("D8029 =", plc.read("D8029"))
    print("\nTesting known valid M bits...")
    for m in ("M8000", "M8001", "M8002", "M8070", "M8071", "M8121", "M8122", "M8123"):
        try:
            print(m, "=", plc.read_bit(m))
        except Exception as e:
            print(m, "FAILED:", e)

finally:
    plc.close()
    
"""
$./test1.py
Connected to 192.168.1.50

Cascading outputs...
Q0 ON
Q0 OFF
Q1 ON
Q1 OFF
Q2 ON
Q2 OFF
Q3 ON
Q3 OFF
Q4 ON
Q4 OFF
Q5 ON
Q5 OFF
Q6 ON
Q6 OFF
Q7 ON
Q7 OFF

Reading D0100...
D0100 = 0

Setting timers T0420 and T0421...
T0420 = {'timer': 420, 'current': 1000, 'preset': 1000, 'status': 0}
T0421 = {'timer': 421, 'current': 9999, 'preset': 1000, 'status': 0}

Reading D0040 as float...
Endian 0 = 1.217
Endian 1 = -21535.8027

Reading D8056...
D8056 = 2775

Reading D8029 Firmware Version Word...
D8029 = 260

Testing known valid M bits...
M8000 = 1
M8001 = 0
M8002 = 0
M8070 = 1
M8071 = 0
M8121 = 1
M8122 = 1
M8123 = 0
"""
    
