#!/usr/bin/env python3

import struct
import sys


def idec_checksum(data):
    checksum = 0

    for offset in range(0, len(data) - 3, 4):
        value = struct.unpack_from("<I", data, offset)[0]
        checksum ^= value

    return checksum


for name in sys.argv[1:]:
    with open(name, "rb") as f:
        data = f.read()

    print(f"{name}: 0x{idec_checksum(data):08x}")
    
"""
# pre-run
dd if=Read_regs.ZNX of=/tmp/HG2F.BIN    bs=1 skip=$((0x02737018)) count=$((0x24cefc)) status=none
dd if=Read_regs.ZNX of=/tmp/HG2F.orig   bs=1 skip=$((0x2737018))  count=$((0x24cefc)) status=none
dd if=Read_regsMod.ZNX of=/tmp/HG2F.mod bs=1 skip=$((0x2737018))  count=$((0x24cefc)) status=none

python3 idec_checksum.py /tmp/os_update.tar.xz  /tmp/project.znv /tmp/HG2F.orig
/tmp/os_update.tar.xz: 0xc02c91a6
/tmp/project.znv: 0x5536c42e
/tmp/HG2F.orig: 0xe6ea3ba9

"""
