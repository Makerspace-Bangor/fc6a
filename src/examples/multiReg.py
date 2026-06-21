#!/usr/bin/env python3
import sys
from fc6a import FC6AMaint
# FIX N-Bytes read in fc6a
'''
Examples:
./multiReg.py 10.10.10.10 200 3 F 0
./multiReg.py 10.10.10.10 200 3 B
# ignore endian in non float tpes.
./multiReg.py 10.10.10.10 200 3 B 1
./multiReg.py 10.10.10.10 200 4 w 
'''

def main():
    if len(sys.argv) < 5:
        print("Usage: multiReg.py <ip> <start_addr> <count> <dtype> [endian]")
        print("  dtype: F = float, W = word, B = bit")
        print("  endian: 0 = little-endian, 1 = big-endian (floats only)")
        print("Example: multiReg.py 10.10.10.10 200 5 F 0")
        sys.exit(1)

    ip = sys.argv[1]
    start_addr = int(sys.argv[2])
    count = int(sys.argv[3])
    dtype = sys.argv[4].upper()

    # default endian = 0; only applies to float reads
    endian = int(sys.argv[5]) if len(sys.argv) == 6 else 0

    plc = None
    try:
        plc = FC6AMaint(ip)

        if dtype == "F":
            values = plc.read_floats_block(start_addr, count, endian=endian)
            print(f"\nPLC: {ip}")
            print(f"Reading {count} FLOATS starting at D{start_addr:04d} (endian={endian})")
            print("-" * 50)
            for i, val in enumerate(values):
                reg = start_addr + (i * 2)
                print(f"FLOAT D{reg:04d}-D{reg+1:04d}: {val:.3f}")

        elif dtype == "W":
            values = plc.read_words_block(start_addr, count)
            print(f"\nPLC: {ip}")
            print(f"Reading {count} WORDS starting at D{start_addr:04d}")
            print("-" * 50)
            for i, val in enumerate(values):
                print(f"WORD D{start_addr + i:04d}: {val}")

        elif dtype == "B":
            values = plc.read_bits_block(start_addr, count)
            print(f"\nPLC: {ip}")
            print(f"Reading {count} BITS starting at M{start_addr:04d}")
            print("-" * 50)
            for i, val in enumerate(values):
                print(f"BIT M{start_addr + i:04d}: {val}")

        else:
            print("Invalid dtype. Must be F, W, or B.")
            sys.exit(1)

        print("-" * 50)

    except Exception as e:
        print(f"Error: {e}")
    finally:
        if plc:
            try:
                plc.close() # implemented, update fc6a
            except Exception:
                pass

if __name__ == "__main__":
    main()
