#!/usr/bin/env python3
from MiSmSerial import MiSmSerial
"""
Purpose: Detect password status on plc.
Tested on FC5A, FC6A and pentra plcs
"""

PROTECTION_STATUS = {
    "0": "Not protected",
    "1": "Write protected",
    "2": "Read protected",
    "3": "Read and write protected",
}


plc = MiSmSerial(
    "/dev/ttyACM0",
    device="FF",
    baud=9600,
    timeout=2.0,
    debug=True,
    bcc_mode="auto",
)

try:
    # RS: Read PLC Operating Status
    reply = plc._xfer("0", "R", "S")
    plc._raise_if_err(reply)

    print()
    print("Raw reply:", reply.raw.hex(" ").upper())
    print("RS data:  ", reply.data)

    if len(reply.data) < 3:
        raise IOError(f"RS reply is too short: {reply.data!r}")

    # RS data layout:
    #   data[0] = RUN/STOP status
    #   data[1] = timer/counter changed status
    #   data[2] = user-program protection status
    protection = reply.data[2:3].decode("ascii")

    if protection not in PROTECTION_STATUS:
        raise IOError(
            f"Unknown protection status {protection!r}: "
            f"raw={reply.raw.hex()}"
        )

    print()
    print(f"Protection value:  {protection}")
    print(f"Protection status: {PROTECTION_STATUS[protection]}")

    if protection == "0":
        print("RESULT: No password protection is reported.")
    else:
        print("RESULT: PLC is password protected.")

finally:
    plc.close()

"""
##### Test 1: FC5A #########

TX(ascii): FF0RS
TX(hex):   05464630525333340d
RX(hex):   063031303030306743373437333933443330433431303030303030303030303030303030303030303030303031460d

Raw reply: 06 30 31 30 30 30 30 67 43 37 34 37 33 39 33 44 33 30 43 34 31 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 31 46 0D
RS data:   b'000gC747393D30C4100000000000000000000000'

Protection value:  0
Protection status: Not protected
RESULT: No password protection is reported.


#### TEST 2: FC6A #######

TX(ascii): FF0RS
TX(hex):   05464630525333340d
RX(hex):   063031303130336e39443035463841443032343431314330304146383930303030303030303030303030303031460d

Raw reply: 06 30 31 30 31 30 33 6E 39 44 30 35 46 38 41 44 30 32 34 34 31 31 43 30 30 41 46 38 39 30 30 30 30 30 30 30 30 30 30 30 30 30 30 30 31 46 0D
RS data:   b'103n9D05F8AD024411C00AF89000000000000000'

Protection value:  3
Protection status: Read and write protected
RESULT: PLC is password protected.

##### Test 3: Pentra #######
TX(ascii): FF0RS
TX(hex):   05464630525333340d
RX(hex):   063031303030304132434446303146464646464646464646464646464646464646464646464646464646464633340d

Raw reply: 06 30 31 30 30 30 30 41 32 43 44 46 30 31 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 46 33 34 0D
RS data:   b'000A2CDF01FFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'

Protection value:  0
Protection status: Not protected
RESULT: No password protection is reported.



"""

