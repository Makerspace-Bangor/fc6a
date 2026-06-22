"""
Force IO doesnt work like I thought it did.

What WindLDR does:
Force IO in the UI enables a function that enables the functions of FORCE IO

Then you have the option force individial IO 

WO = global Force I/O mode
^  = output force enable/release
]  = output forced value
[  = input force enable/release
?  = input forced value

FF0WO1   # enable Force I/O mode
FF0WO0   # disable/suspend Force I/O mode

# Force I7:
FF0W?00071   # set forced input value I7 = ON
FF0W[00071   # enable force on I7

# Force Q7
FF0W]00070   # set forced output value Q7 = OFF
FF0W^00071   # keep/enable force on Q7

"""
