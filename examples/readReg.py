#!/usr/bin/env python3
from fc6a import FC6AMaint
import sys
'''
Read a single register using fc6a lib, using arg[v] style syntax.
not very effiecnt, so only good when reading a few values.
Use:
$readReg.py ip register data-type endian 
H@cker:~/bin$ readReg.py C 2 F 1
IP: C reg: 2 dtype: F endian: 1
-107615024.0
H@cker:~/bin$ readReg.py C 2 F 0
IP: C reg: 2 dtype: F endian: 0
57.70000076293945

'''
PLC_MAP = {
    "A": "10.10.10.10",  # Chamber endian=0
    "B": "10.10.10.30",  # Test Station endian=1
    "C": "10.10.10.57",  # Logger endian=0
    "D": "10.10.10.92",  # E180 endian=0
}

def rread(plc_key, reg, dtype, endian):
    plc_key = plc_key.upper()
    if plc_key not in PLC_MAP:
        sys.exit(f"Invalid PLC alias '{plc_key}'. Use one of: {', '.join(PLC_MAP)}")

    plc = FC6AMaint(PLC_MAP[plc_key])
    reg = int(reg)

    try:
        if dtype == "W":
            return plc.read_word(reg)
        elif dtype == "F":
            swapped = bool(int(endian))
            return round(plc.read_float(reg, swapped), 2)
        elif dtype == "B":
            return plc.read_bits(reg)
        else:
            sys.exit("Invalid data type. Must be W, F, or B.")
    except Exception as e:
        sys.exit(f"Communication error: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 5:
        msg="Usage: readReg.py <A|B|C|D> <register> <W|F|B> <endian(0|1)>\n does not read ranges\nIf the results are whack try flipping the endian"
        #sys.exit("Usage: readReg.py <A|B|C> <register> <W|F|B> <endian(0|1)>")
        sys.exit(f"{msg}")

    ip, reg, dtype, endian = sys.argv[1:]
    val = rread(ip, reg, dtype, endian)
    print(val)
