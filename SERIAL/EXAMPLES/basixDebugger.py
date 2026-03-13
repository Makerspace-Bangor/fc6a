#!/usr/bin/env python3
from datetime import datetime
from MiSmSerial import MiSmSerial
import sys
from time import sleep
from enum import IntFlag, auto
"""
Written without request, or special intersts in mind. 
General Error and informational contexts.
Points of interest:

### ERROR LED ##########
Overcurrent protection function (not a thermal shutdown function).
Overcurrent detected with 4 outputs as 1 group. (Group 1: Q0 to Q3, Group 2: Q4 to Q7, Group 3:
Q10 to Q13, Group 4: Q14 to Q17)
When overcurrent is detected, the 4 outputs in the corresponding group are turned off for a fixed
period (1 s). When overcurrent is detected, a special internal relay turns on (M8172 to M8175) and
the error LED [ERR] turns on

###Battery :: Battery voltage (D8056)
Stores the measured battery voltage in mV. The battery voltage fluctuates according to the usage environment.
When the power is turned on, this value is 65,535 until the initial battery voltage measurement has completed.
This value is 0 when there is a measurement error or when there is no battery.
Battery voltage measurement (M8074)
Shows the battery voltage measurement status.
0: Battery voltage measurement completed
1: Battery voltage being measured
The battery voltage can also be measured by writing 1. The measured value in mV is stored in D8056. The value is reset to 0
 
######### User program execution error:: M8004
######### Comm error:: M8005 page 531 breakdown of Bits 
######### Calendar Errors: M8013, M8014
##### SD CARD ERROR M8255 bit set pg 492 manual
### REcipie err M8265

######### NON ERR POINTS OF INTEREST ##############
firmware: M8029 :: version may relate to functionality
dateTime: D8015 thru D8021  set with M8020

"""


class GeneralError(IntFlag):

    def _generate_next_value_(name, start, count, last_values):
        return 1 << count

    POWER_FAIL = auto()
    TIMER_ERROR = auto()
    DATALINK_CONNECTION_ERROR = auto()
    USER_PROGRAM_ROM_CRC_ERROR = auto()
    TIMER_COUNTER_PRESET_CHANGE_ERROR = auto()
    RESERVED = auto()
    KEEP_DATA_SUM_CHECK_ERROR = auto()
    USER_PROGRAM_SYNTAX_ERROR = auto()
    USER_PROGRAM_DOWNLOAD_ERROR = auto()
    SYSTEM_ERROR = auto()
    CLOCK_ERROR = auto()
    EXPANSION_BUS_INITIALIZATION_ERROR = auto()
    SD_MEMORY_CARD_TRANSFER_ERROR = auto()
    USER_PROGRAM_EXECUTION_ERROR = auto()
    SD_MEMORY_CARD_ACCESS_ERROR = auto()
    #CLEAR_ERRORS = auto()
    
    
PORT = "/dev/ttyACM0"
def get_port(port=PORT):
    entered = input(f"Pres Enter to use COM3, \n else: Enter COM port [{port}]: ").strip()
    print(f"Port Enterned: {entered}")
    return entered if entered else PORT
    
    
def OC_BITS():
	q0 = plc.read_bit("M8170")    
	q1 = plc.read_bit("M8171")    
	q2 = plc.read_bit("M8172")    
	q3 = plc.read_bit("M8173")    
	print(f"OverCurrent: {q0} {q1} {q2} {q3}")
	
def bat_stat():
	v = plc.read("D8056")
	if v == 65535:
		print("batery not initalized")
	else:
		print(f"Voltage {v}")
		
def messure_bat():
	v = plc.read_bit("M8074")  # 0: done measeure 1: mesuring
	w = plc.write_bit("M8074", 1) # measure it.
	if v == 1:
        sleep(0.5)
        v = plc.read_bit("M8074")  # 0: done measeure 1: mesuring		    
   else:
	   print(f"bat Stat: {bat_stat()}")



def get_firmware():
	fw = plc.read("M8029")
	print(f"Firmware version: {fw /100}")


def gen_Err():
    raw = plc.read("D8005")
    flags = GeneralError(raw)

    print(f"D8005: {raw} (0b{raw:016b})")

    if not flags:
        print("No errors")
        return

    for f in GeneralError:
        if f in flags:
            print(f.name)

def clear_errors():
    v = plc.read("D8005")
    plc.write("D8005", v | (1 << 15))


"""
User progr errors:
https://docs.google.com/spreadsheets/d/1mq6s-6IcgdOfDEnF0tq5RbIReAECzsMRR0ijGnsHD2Q/edit?usp=sharing

"""

