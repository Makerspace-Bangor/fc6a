#!/usr/bin/env python3

import argparse
import ipaddress
import os
import socket
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from scapy.all import ARP, Ether, AsyncSniffer, srp1
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

### IF you have multiple networking interfaces, then the program run without spcifications for the interface will crash. 
### TODO : FiX
however, you can specify the address to work around that.
$ sudo python3 hmi_get_ip.py --interface eth1 --assign

### TODO: fix reinstantiation issues
temp fix: $ sudo ip addr flush dev eth1

### unexpected results:
$ sudo python3 hmi_get_ip.py 
[sudo] password for user:   
Listening for HMI ARP requests on enp2s0
Verifying requesters on TCP port 2537
Observation mode only. Use --assign to claim an address.
HMI 192.168.1.20 [00:03:7b:20:08:f1] is looking for 192.168.1.50
HMI 192.168.1.20 [00:03:7b:20:08:f1] is looking for 192.168.1.69  <-- previous connection retained, 
while not having been programmed to the HMI


"""
if os.name == "nt":
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


def tcp_port_open(interface, address, port, timeout):
    """Check a TCP port while forcing traffic through the selected interface."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_BINDTODEVICE,
            interface.encode() + b"\0",
        )
        return sock.connect_ex((address, port)) == 0
    except OSError:
        return False
    finally:
        sock.close()


def address_in_use(interface, address):
    request = Ether(dst="ff:ff:ff:ff:ff:ff") / ARP(op=1, pdst=address)
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


def validate_interface(interface):
    try:
        socket.if_nametoindex(interface)
    except OSError as error:
        raise SystemExit(f"Network interface not found: {interface}") from error


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Watch verified IDEC HMIs for requested local IP addresses."
        )
    )

    parser.add_argument(
        "-i",
        "--interface",
        default="enp2s0",
        help="Ethernet interface (default: enp2s0)",
    )
    parser.add_argument(
        "--hmi-ip",
        help="Only accept requests from this HMI IP",
    )
    parser.add_argument(
        "--hmi-port",
        type=int,
        default=2537,
        help="TCP port used to verify an HMI (default: 2537)",
    )
    parser.add_argument(
        "--connect-timeout",
        type=float,
        default=0.5,
        help="HMI port-check timeout in seconds (default: 0.5)",
    )
    parser.add_argument(
        "--oui",
        default="00:03:7b",
        help="Required IDEC MAC prefix (default: 00:03:7b)",
    )
    parser.add_argument(
        "--prefix",
        type=int,
        default=24,
        help="Subnet prefix used when assigning an address (default: 24)",
    )
    parser.add_argument(
        "--listen-timeout",
        type=float,
        default=10.0,
        help=(
            "Seconds to listen before exiting; use 0 to wait forever "
            "(default: 10)"
        ),
    )
    parser.add_argument(
        "--recheck-interval",
        type=float,
        default=5.0,
        help="Seconds before retrying a failed HMI port check (default: 5)",
    )
    parser.add_argument(
        "--assign",
        action="store_true",
        help="Add the first usable requested address, then exit",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exit after the first verified HMI request",
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

    validate_interface(args.interface)

    if args.hmi_ip:
        try:
            ipaddress.ip_address(args.hmi_ip)
        except ValueError as error:
            raise SystemExit(f"Invalid HMI address: {args.hmi_ip}") from error

    if not 0 <= args.prefix <= 32:
        raise SystemExit("Prefix must be between 0 and 32.")

    if not 1 <= args.hmi_port <= 65535:
        raise SystemExit("HMI port must be between 1 and 65535.")

    if args.listen_timeout < 0:
        raise SystemExit("Listen timeout cannot be negative.")

    if args.recheck_interval < 0:
        raise SystemExit("Recheck interval cannot be negative.")

    verified = set()
    last_checked = {}
    seen_lock = threading.Lock()
    action_lock = threading.Lock()
    stop_event = threading.Event()
    excluded = set(args.exclude)
    oui = args.oui.lower()

    print(f"Listening for HMI ARP requests on {args.interface}")
    print(f"Verifying requesters on TCP port {args.hmi_port}")

    if not args.assign:
        print("Observation mode only. Use --assign to claim an address.")

    executor = ThreadPoolExecutor(max_workers=4)

    def process_candidate(key, source_mac, source_ip, requested_ip):
        if stop_event.is_set():
            return

        if not tcp_port_open(
            args.interface,
            source_ip,
            args.hmi_port,
            args.connect_timeout,
        ):
            return

        if stop_event.is_set():
            return

        with seen_lock:
            if key in verified:
                return
            verified.add(key)

        print(
            f"HMI {source_ip} [{source_mac}] is looking for "
            f"{requested_ip}"
        )

        if not args.assign:
            if args.once or args.hmi_ip:
                stop_event.set()
            return

        with action_lock:
            if stop_event.is_set():
                return

            if requested_ip in excluded:
                print(f"  Ignoring excluded address {requested_ip}")
                return

            try:
                parsed = ipaddress.ip_address(requested_ip)
            except ValueError:
                print("  Ignoring invalid address")
                return

            if parsed.version != 4 or not parsed.is_private:
                print("  Ignoring non-private IPv4 address")
                return

            if parsed.is_loopback or parsed.is_link_local or parsed.is_multicast:
                print("  Ignoring unusable address")
                return

            if requested_ip == source_ip:
                print("  Ignoring the HMI's own address")
                return

            if requested_ip in get_assigned_ips(args.interface):
                print("  Address is already assigned locally")
                stop_event.set()
                return

            if address_in_use(args.interface, requested_ip):
                print("  Address is already in use by another device")
                return

            try:
                add_address(args.interface, requested_ip, args.prefix)
            except subprocess.CalledProcessError as error:
                print(f"  Failed to add address: {error}")
                return

            print(f"  Added {requested_ip}/{args.prefix}")
            print(
                f"  Remove with: sudo ip addr del "
                f"{requested_ip}/{args.prefix} dev {args.interface}"
            )
            stop_event.set()

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

        key = (source_mac, source_ip, requested_ip)
        now = time.monotonic()

        with seen_lock:
            if key in verified:
                return

            previous = last_checked.get(key, 0.0)

            if now - previous < args.recheck_interval:
                return

            last_checked[key] = now

        executor.submit(
            process_candidate,
            key,
            source_mac,
            source_ip,
            requested_ip,
        )

    sniffer = AsyncSniffer(
        iface=args.interface,
        filter="arp",
        prn=handle_packet,
        store=False,
    )

    sniffer.start()

    try:
        if args.listen_timeout > 0:
            stop_event.wait(args.listen_timeout)
        else:
            while not stop_event.wait(0.2):
                pass
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        stop_event.set()

        if sniffer.running:
            sniffer.stop()

        executor.shutdown(wait=True, cancel_futures=True)


if __name__ == "__main__":
    main()
