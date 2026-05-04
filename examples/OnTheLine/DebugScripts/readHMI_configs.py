#!/usr/bin/env python3
from MiSmSerial import MiSmSerial
from time import sleep
PORT = "/dev/ttyACM0"

plc = MiSmSerial(PORT, device="FF", baud=9600, debug=True, bcc_mode="auto")
plc.write_bit("M8022",1)
m8005 = plc.read_bit("M8005")
m8006 = plc.read_bit("M8006")
m8007 = plc.read_bit("M8007")
m8011 = plc.read_bit("M8011")
m8012 = plc.read_bit("M8012")
m8013 = plc.read_bit("M8013")
m8014 = plc.read_bit("M8014")
m8015 = plc.read_bit("M8015")
m8016 = plc.read_bit("M8016")
m8017 = plc.read_bit("M8017")
m8020 = plc.read_bit("M8020")
m8021 = plc.read_bit("M8021")
m8022 = plc.read_bit("M8022")
m8023 = plc.read_bit("M8023")

print(f"M8005: {m8005}")
print(f"M8006: {m8006}")
print(f"M8007: {m8007}")
print(f"M8011: {m8011}")
print(f"M8012: {m8012}")
print(f"M8013: {m8013}")
print(f"M8014: {m8014}")
print(f"M8015: {m8015}")
print(f"M8016: {m8016}")
print(f"M8017: {m8017}")
print(f"M8020: {m8020}")
print(f"M8021: {m8021}")
print(f"M8022: {m8022}")
print(f"M8023: {m8023}")

#plc.write_bit("M8022",0)
'''
This is a serial example in the nework eaxmple code. But I used it, and will likely use others like it.
well this whole project needs a reorginzation and refactor, so dont worry about it for now.

Here Im reading all the registers I suspect to be HMI Config bits.
They were all zero. untill I made m8022 1 for giggles.

TX(ascii): FF0Wm80221
TX(hex):   05464630576d383032323133360d
RX(hex):   0630313033370d
TX(ascii): FF0Rm8005
TX(hex):   05464630526d3830303530370d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8006
TX(hex):   05464630526d3830303630340d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8007
TX(hex):   05464630526d3830303730350d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8011
TX(hex):   05464630526d3830313130320d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8012
TX(hex):   05464630526d3830313230310d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8013
TX(hex):   05464630526d3830313330300d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8014
TX(hex):   05464630526d3830313430370d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8015
TX(hex):   05464630526d3830313530360d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8016
TX(hex):   05464630526d3830313630350d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8017
TX(hex):   05464630526d3830313730340d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8020
TX(hex):   05464630526d3830323030300d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8021
TX(hex):   05464630526d3830323130310d
RX(hex):   063031303030370d
TX(ascii): FF0Rm8022
TX(hex):   05464630526d3830323230320d
RX(hex):   063031303130360d
TX(ascii): FF0Rm8023
TX(hex):   05464630526d3830323330330d
RX(hex):   063031303030370d
M8005: 0
M8006: 0
M8007: 0
M8011: 0
M8012: 0
M8013: 0
M8014: 0
M8015: 0
M8016: 0
M8017: 0
M8020: 0
M8021: 0
M8022: 1
M8023: 0


'''

