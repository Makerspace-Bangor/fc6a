#!/usr/bin/env python3
import time
from MiSmTCP import MiSmTCP
"""
Flash the PLC status LED so you know which PLC is running the code.
adjust the CPU module analog controls and monitor for changes.
"""
PLC_IP = "192.168.1.2"
POLL_INTERVAL = 0.1
LED_INTERVAL = 0.5

plc = MiSmTCP(PLC_IP, device="FF", timeout=2.0)

last_values = None
led_state = False
next_led_toggle = time.monotonic()

try:
    while True:
        now = time.monotonic()

        if now >= next_led_toggle:
            led_state = not led_state
            plc.write_bit("M8010", led_state)
            next_led_toggle = now + LED_INTERVAL

        values = (
            plc.read("D8057"),
            plc.read("D8058"),
            plc.read("D8059"),
            plc.read("D8060"),
        )

        if values != last_values:
            trimmer, analog_in, trimmer_status, analog_status = values

            print(
                f"Trimmer: {trimmer}  "
                f"Trimmer Status: {trimmer_status}  "
                f"Analog In: {analog_in}  "
                f"Analog Status: {analog_status}"
            )

            last_values = values

        time.sleep(POLL_INTERVAL)

except KeyboardInterrupt:
    print("\nStopping")

finally:
    try:
        plc.write_bit("M8010", False)
    finally:
        plc.close()
