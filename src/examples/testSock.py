#!/usr/bin/env python3
import socket
ip="192.168.1.32"
port="2101"
s = socket.socket()
s.settimeout(5)
s.connect((ip,port))
print("PLC Connected")
"""
Dumps a bunch of junk if not success
"""
