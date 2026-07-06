#!/usr/bin/env python3
from ftplib import FTP
import random, string

ip = "192.168.1.150"
user = ''.join(random.choice('0123456789abcdef') for _ in range(16))
pw   = ''.join(random.choice('0123456789abcdef') for _ in range(15))

print("trying")
print("USER", user)
print("PASS", pw)

ftp = FTP()
ftp.connect(ip, 2539, timeout=5)
print(ftp.getwelcome())
ftp.login(user, pw)
print("LOGIN OK")
print("PWD:", ftp.pwd())
print("Port: 2537")
ftp.quit()
