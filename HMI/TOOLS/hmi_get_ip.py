#!/usr/bin/env python3

import argparse
import ipaddress
import os
import subprocess
import sys
from scapy.all import ARP, Ether, sniff, srp1
"""
Linux only lol.
sudo apt install python3-scapy

Requires sudo priviligdges to run. 
This program finds your IDEC HMI, and the IP addres of the PLC it wants
to communicate with, then TEMPORAILY sets your IP to the IP your HMI wants.

Not the smartest program, you still need to know your HMI IP. 
To find that:
    Press and Hold the top left corner of the HMI screen for 5-10 seconds.
    The Maintenance screen appears.
    Press System Mode button.
    (screen may go blank for a few seconds)
    Center, lower third, View the "Wired IP Address"
    This is your HMI IP.
    Press Run to return to normal operation.
    
#obsurvational example:

$sudo python3 hmi_get_ip.py --hmi-ip 192.168.1.20
[sudo] password for user:   
Listening for HMI ARP requests on enp2s0
Observation mode only. Use --assign to claim addresses.
HMI 192.168.1.20 [00:03:7b:20:08:f1] is looking for 192.168.1.50

$sudo python3 hmi_get_ip.py --hmi-ip 192.168.1.20 --assign

$ ip -4 addr show dev enp2s0
2: enp2s0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UP group default qlen 1000
    inet 192.168.1.69/24 scope global enp2s0
       valid_lft forever preferred_lft forever
    inet 192.168.1.50/24 scope global secondary enp2s0 <--secondary address assigned.
       valid_lft forever preferred_lft forever
       
TODO: exit when the IP is assigned, stop scanning.       
"""
if os.name == 'nt':
    print("Windows not supported")
    sys.exit(1)


def get_assigned_ips(interface):
    result = subprocess.run(
        ["ip", "-4", "-o", "addr", "show", "dev", interface],
        capture_output=True,
        text=True,
        check=True,
    )

    addresses = set()

    for line in result.stdout.splitlines():
        fields = line.split()

        if "inet" in fields:
            value = fields[fields.index("inet") + 1]
            addresses.add(value.split("/")[0])

    return addresses


def address_in_use(interface, address):
    request = (
        Ether(dst="ff:ff:ff:ff:ff:ff")
        / ARP(op=1, pdst=address)
    )

    reply = srp1(
        request,
        iface=interface,
        timeout=0.75,
        verbose=False,
    )

    return reply is not None


def add_address(interface, address, prefix):
    subprocess.run(
        ["ip", "addr", "add", f"{address}/{prefix}", "dev", interface],
        check=True,
    )


def main():
    parser = argparse.ArgumentParser(
        description="Watch an IDEC HMI for requested local IP addresses."
    )

    parser.add_argument(
        "-i",
        "--interface",
        default="enp2s0",
        help="Ethernet interface",
    )

    parser.add_argument(
        "--hmi-ip",
        help="Only accept requests from this HMI IP",
    )

    parser.add_argument(
        "--oui",
        default="00:03:7b",
        help="Required HMI MAC prefix",
    )

    parser.add_argument(
        "--prefix",
        type=int,
        default=24,
        help="Subnet prefix used when assigning an address",
    )

    parser.add_argument(
        "--assign",
        action="store_true",
        help="Automatically add requested addresses",
    )

    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Address to ignore; may be specified more than once",
    )

    args = parser.parse_args()

    if os.geteuid() != 0:
        raise SystemExit("Run this script with sudo.")

    seen = set()
    excluded = set(args.exclude)
    oui = args.oui.lower()

    print(f"Listening for HMI ARP requests on {args.interface}")

    if not args.assign:
        print("Observation mode only. Use --assign to claim addresses.")

    def handle_packet(packet):
        if Ether not in packet or ARP not in packet:
            return

        arp = packet[ARP]

        if arp.op != 1:
            return

        source_mac = packet[Ether].src.lower()
        source_ip = arp.psrc
        requested_ip = arp.pdst

        if not source_mac.startswith(oui):
            return

        if args.hmi_ip and source_ip != args.hmi_ip:
            return

        key = (source_mac, requested_ip)

        if key in seen:
            return

        seen.add(key)

        print(
            f"HMI {source_ip} [{source_mac}] is looking for "
            f"{requested_ip}"
        )

        if not args.assign:
            return

        if requested_ip in excluded:
            print(f"  Ignoring excluded address {requested_ip}")
            return

        try:
            parsed = ipaddress.ip_address(requested_ip)
        except ValueError:
            print("  Ignoring invalid address")
            return

        if not parsed.is_private:
            print("  Ignoring non-private address")
            return

        if requested_ip == source_ip:
            print("  Ignoring the HMI's own address")
            return

        if requested_ip in get_assigned_ips(args.interface):
            print("  Address is already assigned locally")
            return

        if address_in_use(args.interface, requested_ip):
            print("  Address is already in use by another device")
            return

        add_address(args.interface, requested_ip, args.prefix)

        print(f"  Added {requested_ip}/{args.prefix}")
        print(
            f"  Remove with: sudo ip addr del "
            f"{requested_ip}/{args.prefix} dev {args.interface}"
        )

    sniff(
        iface=args.interface,
        filter="arp",
        prn=handle_packet,
        store=False,
    )


if __name__ == "__main__":
    main()
