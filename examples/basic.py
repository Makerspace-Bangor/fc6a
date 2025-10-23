#!/usr/bin/env python3
from fc6a import FC6AMaint
from time import sleep
plc = FC6AMaint("192.168.1.3")
reg=6969
mbit=8125
# Read bit M
bit = plc.read_bits(mbit)
print(f"{mbit} =", bit)

# Turn plc off
print("Turn off PLC")
plc.write_bit(mbit, True)
sleep(2)

# Read bit M
bit = plc.read_bits(mbit)
print(f"{mbit} =", bit)
sleep(5)
# Turn plc off
plc.write_bit(mbit, True)
sleep(2)
# Read bit M
bit = plc.read_bits(mbit)
print("Is it on??")
print(f"{mbit} =", bit)
sleep(5)


# Read D2000 (word)
word = plc.read_word(reg)
print("D2000 =", word)

# Write D2001 = 1234
plc.write_word(reg, 420)
sleep(3)
# Read D2000 (word)
word = plc.read_word(reg)
print("D2000 =", word)

# Read float D3610
fval = plc.read_float(reg)
print(f"{reg} =", fval)

# Write float 25.7 to D3612
plc.write_float(reg, 25.7)
sleep(1)
# Read float D3610
fval = plc.read_float(reg)
print(f"{reg} =", fval)
