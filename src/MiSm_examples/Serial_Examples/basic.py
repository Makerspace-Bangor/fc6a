#!/usr/bin/env python3

import os

from MiSmSerial import MiSmSerial



if os.name == "nt": 
	PORT = "COM3" 
else: 
    PORT = "/dev/ttyACM0"


def main():
    plc = MiSmSerial(
        PORT,
        baud=9600,
        timeout=1.0,
        bcc_mode="auto",
    )

    try:
        print(f"Connected to {PORT}")

        # Read individual bit and word registers.
        print("M0000:", plc.read_bit("M", 0))
        print("D0000:", plc.read_word("D", 0))

        # Read several consecutive registers.
        print("M0000-M0007:", plc.read_bits("M", 0, 8))
        print("D0000-D0003:", plc.read_words("D", 0, 4))

        # Example writes. Uncomment when appropriate.
        # plc.write_bit("M", 0, 1)
        # plc.write_word("D", 0, 1234)

    finally:
        plc.close()
        print("Connection closed")


if __name__ == "__main__":
    main()
