#!/usr/bin/env python3
"""
MiSmSDCard is a library for MiSmTCP and MiSmSerial to acess 
SD Card File IO operations. works reliably on serial.
TCP fails randomly, with partial reads. I think the packet size / rate
might be a factor. Not sure, tired.

$testWalk.py
walk the SD Card file system report files an folders 
"""

from MiSmTCP import MiSmTCP
from MiSmSDCard import MiSmSDCard

PLC_IP = "192.168.1.1"

#plc = MiSmTCP(PLC_IP)
plc = MiSmTCP(PLC_IP, debug=False)
plc.SD = MiSmSDCard(plc)

try:
    plc.SD.walkSD("/")
finally:
    plc.close()

"""

Works great, most of the time. fails randomly, havent figuref out why.
great, now that I want it to fail, so I can paste the error, it wont. 
it say timeout basicly. 
prints part of your file tree, then times out.

"""
