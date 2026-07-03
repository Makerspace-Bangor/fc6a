#!/usr/bin/env python3

from MiSmTCP import MiSmTCP
from MiSmSDCard import MiSmSDCard

PLC_IP = "192.168.1.1"

plc = MiSmTCP(PLC_IP)

try:
    plc.SD.walkSD("/")
finally:
    plc.close()
