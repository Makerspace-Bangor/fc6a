#!/usr/bin/env python3

from MiSmTCP import MiSmTCP
from time import sleep
PLC_IP = "192.168.1.1"

plc = MiSmTCP(PLC_IP, debug=False)
plc.release_force()
#plc.force("Q1", 0)
#print("Q1 forced")
"""
Normal output writes may have no effect if the 
PLC program conflicts with those commands 

pre run state: Q1, Q6 are on.

"""
for i in range(8):
    plc.output(f"Q{i}", 1)
sleep(5)
for i in range(8):
    plc.output(f"Q{i}", 0)    

""" Force all low """    
for i in range(8):    
    plc.force(f"Q{i}",0)

print("Normal write has no effect because force IO is set")
sleep(10)
for i in range(8):
    plc.output(f"Q{i}", 0)
sleep(3)    
for i in range(8):
    plc.output(f"Q{i}", 1)    

print("Force is on from the previous force")
""" Force all high """
for i in range(8):    
    plc.force(f"Q{i}",1)

sleep(5)
plc.write("Q1", 1) # lets see if the sigal to enable is retained. 

plc.release_force()
"""
return to nominal program state.

I think I kinda knew it before, but you can have both 
the serial and TCP connections active concurently. 
So from this program I can watch the Force state change in windLDR
which I think is neat.
"""
