#!/usr/bin/env python3
import ipaddress
import socket
from scapy.all import ARP, Ether, srp
"""
If port 2537 is open, and the mac is the idec prefix, 
then we have found an HMI.
This program is only to ID HMIs on your network. 
sudo apt install python3-scapy
or pip install scapy
"""
NETWORK = "192.168.1.0/24"
INTERFACE = "enp2s0"
IDEC_PREFIX = "00:03:7b"
PORT = 2537
TIMEOUT = 0.2

def port_open(ip):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(TIMEOUT)
    try:
        s.connect((ip, PORT))
        return True
    except OSError:
        return False
    finally:
        s.close()

print(f"Detecting HMI IP on Network: {NETWORK}")
print("Scanning...\n")

for ip in ipaddress.ip_network(NETWORK).hosts():
    ip = str(ip)
    pkt = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(pdst=ip)
    ans, _ = srp(
        pkt,
        iface=INTERFACE,
        timeout=0.1,
        verbose=False
    )

    if not ans:
        continue

    mac = ans[0][1].hwsrc.lower()

    if not mac.startswith(IDEC_PREFIX):
        continue

    if not port_open(ip):
        continue

    print(f"{ip:15} {mac} HMI PORT {PORT}")
