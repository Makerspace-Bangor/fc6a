#!/usr/bin/env python3
from MiSmTCP import MiSmTCP
# https://github.com/Makerspace-Bangor/fc6a/blob/main/documentation/PLC_Docs/FC6A_UserMan_registers.pdf
# See page 46

# FC6A Expansion Module Type IDs
# Source: FC6A_UserMan_registers.pdf, page 46
#
# +---------+-----------+----------------------------------------------+
# | Type ID | Binary    | Type No.                                     |
# +---------+-----------+----------------------------------------------+
# | 0x00    | 0000 0000 | FC6A-N16B1, FC6A-N16B3                       |
# | 0x01    | 0000 0001 | FC6A-R161, FC6A-T16K1, FC6A-T16P1,           |
# |         |           | FC6A-T16K3, FC6A-T16P3                       |
# | 0x02    | 0000 0010 | FC6A-N32B3                                   |
# | 0x03    | 0000 0011 | FC6A-T32K3, FC6A-T32P3                       |
# | 0x04    | 0000 0100 | FC6A-N08B1, FC6A-N08A11                      |
# | 0x05    | 0000 0101 | FC6A-R081, FC6A-T08K1, FC6A-T08P1            |
# | 0x06    | 0000 0110 | FC6A-M08BR1                                  |
# | 0x07    | 0000 0111 | FC6A-M24BR1                                  |
# | 0x18    | 0001 1000 | FC6A-PH1                                     |
# | 0x19    | 0001 1001 | FC6A-EXM2                                    |
# | 0x1A    | 0001 1010 | FC6A-EXM1S                                   |
# | 0x20    | 0010 0000 | FC6A-J2C1                                    |
# | 0x21    | 0010 0001 | FC6A-J4A1                                    |
# | 0x22    | 0010 0010 | FC6A-J8A1                                    |
# | 0x24    | 0010 0100 | FC6A-K4A1                                    |
# | 0x25    | 0010 0101 | FC6A-L06A1                                   |
# | 0x26    | 0010 0110 | FC6A-L03CN1                                  |
# | 0x27    | 0010 0111 | FC6A-J4CN1                                   |
# | 0x28    | 0010 1000 | FC6A-J8CU1                                   |
# | 0x29    | 0010 1001 | FC6A-F2M1                                    |
# | 0x2A    | 0010 1010 | FC6A-F2MR1                                   |
# | 0x2B    | 0010 1011 | FC6A-J4CH1Y                                  |
# | 0x2C    | 0010 1100 | FC6A-EXM1M                                   |
# | 0x2E    | 0010 1110 | FC6A-SIF52                                   |
# | 0xFF    | 1111 1111 | Not connected                                |
# +---------+-----------+----------------------------------------------+
PLC_IP = "192.168.1.6"

plc = MiSmTCP(PLC_IP, device="FF", timeout=2.0)


def read_word(address):
    value = plc.read(f"D{address:04d}")
    return int(value) & 0xFFFF


def show_info(name, info_address, version_address):
    info = read_word(info_address)
    version = read_word(version_address)

    print(
        f"{name:20s} "
        f"D{info_address:04d}=0x{info:04X} "
        f"D{version_address:04d}=0x{version:04X} "
        f"high=0x{(info >> 8) & 0xFF:02X} "
        f"low=0x{info & 0xFF:02X}"
    )


try:
    print("CPU option and cartridge information")
    print("------------------------------------")

    show_info("HMI module", 8120, 8121)
    show_info("Cartridge slot 1", 8122, 8123)
    show_info("Cartridge slot 2", 8124, 8125)
    show_info("Cartridge slot 3", 8126, 8127)

    print("\nExpansion module information")
    print("----------------------------")

    for slot in range(1, 16):
        info_address = 8470 + ((slot - 1) * 2)
        version_address = info_address + 1

        show_info(
            f"Expansion slot {slot}",
            info_address,
            version_address,
        )

finally:
    plc.close()

"""
CPU option and cartridge information
------------------------------------
HMI module           D8120=0x83FF D8121=0x0000 high=0x83 low=0xFF
Cartridge slot 1     D8122=0x83FF D8123=0x0000 high=0x83 low=0xFF
Cartridge slot 2     D8124=0x83FF D8125=0x0000 high=0x83 low=0xFF
Cartridge slot 3     D8126=0x83FF D8127=0x0000 high=0x83 low=0xFF

Expansion module information
----------------------------
Expansion slot 1     D8470=0x0026 D8471=0x0167 high=0x00 low=0x26
Expansion slot 2     D8472=0x83FF D8473=0x0000 high=0x83 low=0xFF
Expansion slot 3     D8474=0x83FF D8475=0x0000 high=0x83 low=0xFF
Expansion slot 4     D8476=0x83FF D8477=0x0000 high=0x83 low=0xFF
Expansion slot 5     D8478=0x83FF D8479=0x0000 high=0x83 low=0xFF
Expansion slot 6     D8480=0x83FF D8481=0x0000 high=0x83 low=0xFF
Expansion slot 7     D8482=0x83FF D8483=0x0000 high=0x83 low=0xFF
Expansion slot 8     D8484=0x83FF D8485=0x0000 high=0x83 low=0xFF
Expansion slot 9     D8486=0x83FF D8487=0x0000 high=0x83 low=0xFF
Expansion slot 10    D8488=0x83FF D8489=0x0000 high=0x83 low=0xFF
Expansion slot 11    D8490=0x83FF D8491=0x0000 high=0x83 low=0xFF
Expansion slot 12    D8492=0x83FF D8493=0x0000 high=0x83 low=0xFF
Expansion slot 13    D8494=0x83FF D8495=0x0000 high=0x83 low=0xFF
Expansion slot 14    D8496=0x83FF D8497=0x0000 high=0x83 low=0xFF
Expansion slot 15    D8498=0x83FF D8499=0x0000 high=0x83 low=0xFF


------------------
(program exited with code: 0)
Press return to continue



"""
