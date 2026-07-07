#!/usr/bin/env python3
from MiSmTCP import MiSmTCP

def mac_from_words(words):
    return ":".join(f"{w & 0xFF:02X}" for w in words)

for ip in range(2, 6):
    host = f"192.168.1.{ip}"

    try:
        plc = MiSmTCP(host, timeout=5.0)
        mac1 = mac_from_words(plc.read_block("D8324", count=6))
        mac2 = mac_from_words(plc.read_block("D8651", count=6))

        print(host)
        print(f"  D8324-D8329 : {mac1}")
        print(f"  D8651-D8656 : {mac2}\n")
        plc.close()

    except OSError as e:
        print(f"{host} connection failed: {e}\n")

    except Exception as e:
        print(f"{host}  read failed: {e}\n")
