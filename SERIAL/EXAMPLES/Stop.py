#!/usr/bin/env python3
from MiSmSerial import MiSmSerial

PORT = "/dev/ttyACM0"

plc = MiSmSerial(
    PORT,
    device="FF",
    baud=9600,
    debug=True,
    bcc_mode="auto",
)

try:
	  # watchout Virtualbox with FK with your ports. 
    # Turn OFF M8000 (put PLC no RUN)
    plc.write_bit("M8000", 0)
    print("M8000 set to 0 (STOP).")

finally:
    plc.close()
