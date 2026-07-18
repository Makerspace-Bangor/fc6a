#!/usr/bin/env python3
from MiSmSerial import MiSmSerial

PORT = "/dev/ttyACM0"


GENERAL_ERROR_BITS = {
    0: "POWER_FAIL",
    1: "TIMER_ERROR",
    2: "DATALINK_CONNECTION_ERROR",
    3: "USER_PROGRAM_ROM_CRC_ERROR",
    4: "TIMER_COUNTER_PRESET_CHANGE_ERROR",
    5: "RESERVED",
    6: "KEEP_DATA_SUM_CHECK_ERROR",
    7: "USER_PROGRAM_SYNTAX_ERROR",
    8: "USER_PROGRAM_DOWNLOAD_ERROR",
    9: "SYSTEM_ERROR",
    10: "CLOCK_ERROR",
    11: "EXPANSION_BUS_INITIALIZATION_ERROR",
    12: "SD_MEMORY_CARD_TRANSFER_ERROR",
    13: "USER_PROGRAM_EXECUTION_ERROR",
    14: "SD_MEMORY_CARD_ACCESS_ERROR",
    15: "CLEAR_ERRORS_CONTROL_BIT",
}

USER_EXECUTION_ERRORS = {
    0: "NO_ERROR",
    1: "Source/destination device exceeds range",
    2: "MUL result exceeds data type range",
    3: "DIV result exceeds data type range, or division by 0",
    4: "BCDLS has S1 or S1+1 exceeding 9999",
    5: "HTOB input too large",
    6: "BTOH has a digit exceeding 9",
    7: "HTOA/ATOH/BTOA/ATOB digit count out of range",
    8: "ATOH/ATOB has non-ASCII data",
    9: "WEEK instruction time data out of range",
    10: "YEAR instruction date data out of range",
    11: "DGRD range exceeded",
    12: "CVXTY/CVYTX executed without matching XYFS",
    13: "CVXTY/CVYTX S2 exceeds value specified in XYFS",
    14: "Label in LJMP, LCAL, or DJNZ not found",
    15: "Reserved/undefined",
    16: "PID/PIDA instruction execution error",
    17: "Reserved/undefined",
    18: "Instruction cannot be used in interrupt program",
    19: "Instruction not available for this PLC",
    20: "Pulse output instruction has invalid values",
    21: "DECO has S1 exceeding 255",
    22: "BCNT has S2 exceeding 256",
    23: "ICMP>= has S1 < S3",
    24: "Reserved/undefined",
    25: "BCDLS has S2 exceeding 7",
    26: "Interrupt input or timer interrupt not programmed",
    27: "Work area broken",
    28: "Trigonometric/data type instruction source invalid",
    29: "Float/data type instruction result exceeds range",
    30: "SFTL/SFTR exceeds valid range",
    31: "FOEX/FIFO used before FIFO data file registered",
    32: "TADD, TSUB, HOUR, or HTOS has invalid source data",
    33: "RNDM has invalid data",
    34: "NDSRC has invalid source data",
    35: "SUM result exceeds valid range",
    36: "CSV file exceeds maximum size",
    37: "Reserved/undefined",
    38: "Reserved/undefined",
    39: "Reserved/undefined",
    40: "Reserved/undefined",
    41: "SD memory card is write protected",
    42: "A script failed",
    43: "Reserved/undefined",
    44: "Reserved/undefined",
    45: "Reserved/undefined",
    46: "SCALE instruction out of range",
    47: "Reserved/undefined",
    48: "Pulse collisions / timing errors",
    49: "Pulse output not initialized properly",
}


def read_word(plc, addr):
    try:
        return plc.read(addr)
    except Exception as e:
        return f"READ_ERROR: {e}"


def read_bit(plc, addr):
    try:
        return plc.read_bit(addr)
    except Exception as e:
        return f"READ_ERROR: {e}"


def bits16(value):
    return f"{value:016b}"


def on_bits(value, width=16):
    return [i for i in range(width) if (value >> i) & 1]


def decode_general_errors(value):
    active = []
    for bit in range(16):
        if (value >> bit) & 1:
            active.append((bit, GENERAL_ERROR_BITS.get(bit, "UNKNOWN")))
    return active


def battery_text(v):
    if isinstance(v, str):
        return v
    if v == 65535:
        return "not initialized yet"
    if v == 0:
        return "measurement error or no battery"
    return f"{v} mV"


def text_onoff(v):
    if isinstance(v, str):
        return v
    return "ON" if v else "OFF"


def user_exec_text(code):
    if isinstance(code, str):
        return code
    return USER_EXECUTION_ERRORS.get(code, "Unknown execution error code")


def main():
    plc = MiSmSerial(PORT, device="FF", baud=9600, debug=False, bcc_mode="auto")

    try:
        fw = read_word(plc, "D8029")

        d8004 = read_word(plc, "D8004")
        d8005 = read_word(plc, "D8005")
        d8006 = read_word(plc, "D8006")
        d8056 = read_word(plc, "D8056")

        m8000 = read_bit(plc, "M8000")
        m8002 = read_bit(plc, "M8002")
        m8004 = read_bit(plc, "M8004")
        m8005 = read_bit(plc, "M8005")
        m8010 = read_bit(plc, "M8010")
        m8013 = read_bit(plc, "M8013")
        m8014 = read_bit(plc, "M8014")
        m8025 = read_bit(plc, "M8025")
        m8070 = read_bit(plc, "M8070")
        m8071 = read_bit(plc, "M8071")
        m8074 = read_bit(plc, "M8074")
        m8172 = read_bit(plc, "M8172")
        m8173 = read_bit(plc, "M8173")
        m8174 = read_bit(plc, "M8174")
        m8175 = read_bit(plc, "M8175")
    finally:
        plc.close()

    print()
    print("==== FC6A PLC DIAGNOSTIC REPORT ====")

    if isinstance(fw, str):
        print(f"Firmware              : {fw}")
    else:
        print(f"Firmware              : {fw / 100:.2f}")

    print()
    print("CPU / STATUS")
    print(f"Run command M8000     : {text_onoff(m8000)}")
    print(f"All outputs off M8002 : {text_onoff(m8002)}")
    print(f"Exec error M8004      : {text_onoff(m8004)}")
    print(f"Comm error M8005      : {text_onoff(m8005)}")
    print(f"Status LED M8010      : {text_onoff(m8010)}")
    print(f"Clock wr err M8013    : {text_onoff(m8013)}")
    print(f"Clock rd err M8014    : {text_onoff(m8014)}")
    print(f"Keep outputs M8025    : {text_onoff(m8025)}")

    print()
    print("SD / BATTERY")
    print(f"SD mounted M8070      : {text_onoff(m8070)}")
    print(f"SD accessing M8071    : {text_onoff(m8071)}")
    print(f"Battery measure M8074 : {text_onoff(m8074)}")
    print(f"Battery D8056         : {battery_text(d8056)}")

    print()
    print("OVERCURRENT")
    print(f"Group 1 M8172         : {text_onoff(m8172)}")
    print(f"Group 2 M8173         : {text_onoff(m8173)}")
    print(f"Group 3 M8174         : {text_onoff(m8174)}")
    print(f"Group 4 M8175         : {text_onoff(m8175)}")

    print()
    print("REGISTERS")

    if isinstance(d8004, str):
        print(f"D8004                 : {d8004}")
    else:
        print(f"D8004                 : {d8004}  bits:{bits16(d8004)}  on:{on_bits(d8004)}")

    if isinstance(d8005, str):
        print(f"D8005                 : {d8005}")
    else:
        print(f"D8005                 : {d8005}  bits:{bits16(d8005)}  on:{on_bits(d8005)}")
        decoded = decode_general_errors(d8005)
        if decoded:
            print("D8005 decoded:")
            for bit, name in decoded:
                print(f"  bit {bit:>2} : {name}")
        else:
            print("D8005 decoded:")
            print("  no active general error bits")

    if isinstance(d8006, str):
        print(f"D8006                 : {d8006}")
    else:
        print(f"D8006                 : {d8006}")
        print(f"D8006 meaning         : {user_exec_text(d8006)}")

    print("====================================")
    print()


if __name__ == "__main__":
    main()
