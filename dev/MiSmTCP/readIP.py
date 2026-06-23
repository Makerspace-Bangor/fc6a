#!/usr/bin/env python3

from MiSmTCP import MiSmTCP

PLC_IP = "192.168.1.1"

plc = MiSmTCP(PLC_IP, debug=True)

try:
    words = plc.read_block("D8304", count=4, endian=0)

    print("Read:")
    for i, w in enumerate(words):
        print(f"D{8304+i:04d} = {w}")

    # write the same values back as a test
    #plc.write_block("D8304", words, endian=1)

    #plc.write_block("D0064", [192, 168, 1, 69])
    #plc.write_block("D0064", [192, 168, 1, 69], endian=1)
    plc.write_unit("D0064", 6969, 4, endian=0)
    """
    here you end up with:
    D0064 0
    D0065 0
    D0066 0
    D0067 6969
    (depending on endian)
    """
    
 

finally:
    plc.close()
