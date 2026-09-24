#!/usr/bin/env python3
"""Discover IDEC HMIs and optionally serve a small zero-filled fake PLC."""
import argparse
import ipaddress
import platform
import re
import socket
import subprocess
import sys
import threading
import time
# IDEC MAC
OUI = '00:03:7b'
"""
find your HMI, configure the network for coms, and fake a PLC which the HMI Wants.

sudo python3 hmi_find.py --host 192.168.1.0/24 -I enp0s25
"""
ver = "9.24.2026_v1"
print(f"hmi_find {ver}")

def bcc(body):
    value = 0
    for byte in body:
        value ^= byte
    return f'{value:02X}'.encode()


def response(frame):
    """Conservative maintenance replies. Unsupported commands receive no response."""
    if not frame.startswith(b'\x05') or not frame.endswith(b'\r'):
        return None
    body = frame[:-3]
    if bcc(body).upper() != frame[-3:-1].upper() or len(body) < 6:
        return None
    head, command = body[1:4], body[4:6]
    if command[:1] == b'R':
        match = re.match(rb'([0-9]{4})([0-9A-Fa-f]{2})', body[6:])
        if not match:
            return None
        count = int(match.group(2), 16)
        if count > 64:
            return None
        payload = b'0' * (2 * count)
    elif command[:1] == b'W':
        payload = b''
    else:
        return None
    reply = b'\x06' + head + payload
    return reply + bcc(reply) + b'\r'


def serve_client(client, peer):
    with client:
        client.settimeout(2)
        data = b''
        while True:
            try:
                chunk = client.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                return
            data += chunk
            while b'\r' in data:
                frame, data = data.split(b'\r', 1)
                reply = response(frame + b'\r')
                if reply:
                    client.sendall(reply)
                else:
                    print(f'Unsupported request from {peer[0]}: {(frame + bytes([13])).hex(" ")}')
            if len(data) > 65536:
                return


def serve(addresses):
    listeners = []
    for address in addresses:
        sock = socket.socket()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((address, 2101))
        sock.listen(8)
        listeners.append(sock)
        print(f'Fake PLC listening on {address}:2101 (zero-filled reads)')
    try:
        while True:
            for sock in listeners:
                sock.settimeout(0.5)
                try:
                    client, peer = sock.accept()
                except socket.timeout:
                    continue
                threading.Thread(target=serve_client, args=(client, peer), daemon=True).start()
    finally:
        for sock in listeners:
            sock.close()


def alias_command(iface, address, prefix, add):
    if platform.system() == 'Windows':
        mask = str(ipaddress.IPv4Network(f'0.0.0.0/{prefix}').netmask)
        if add:
            return ['netsh', 'interface', 'ipv4', 'add', 'address', f'name={iface}',
                    f'address={address}', f'mask={mask}', 'store=active']
        return ['netsh', 'interface', 'ipv4', 'delete', 'address', f'name={iface}',
                f'address={address}']
    return ['ip', '-4', 'addr', 'add' if add else 'del', f'{address}/{prefix}', 'dev', iface]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, metavar='CIDR',
                        help='candidate HMI subnet, e.g. 192.168.1.0/24')
    parser.add_argument('-I', '--interface', required=True, help='OS interface name')
    parser.add_argument('--seconds', type=float, default=12, help='ARP observation time')
    parser.add_argument('--no-prompt', action='store_true')
    args = parser.parse_args()
    network = ipaddress.ip_network(args.host, strict=False)
    if network.version != 4 or network.num_addresses > 4096:
        parser.error('supply an IPv4 range of at most 4096 addresses')
    try:
        from scapy.all import ARP, Ether, conf, sniff, srp
    except ImportError:
        parser.error('install Scapy: python -m pip install scapy (Windows also needs Npcap)')
    conf.verb = 0
    if args.interface not in [dev.name for dev in conf.ifaces.values()]:
        parser.error(f'interface {args.interface!r} is not visible to Scapy')
    # Passive sniffing starts before active probes so requests during the scan are captured.
    observed = []
    stop = threading.Event()

    def capture():
        sniff(iface=args.interface, filter='arp', timeout=args.seconds,
              prn=lambda packet: observed.append((time.monotonic(), packet)))
        stop.set()

    worker = threading.Thread(target=capture, daemon=True)
    worker.start()
    time.sleep(0.3)
    found = {}
    for offset in range(0, network.num_addresses, 256):
        hosts = list(network.hosts())[offset:offset + 256]
        if not hosts:
            continue
        probe = Ether(dst='ff:ff:ff:ff:ff:ff') / ARP(pdst=[str(ip) for ip in hosts])
        answers, _ = srp(probe, iface=args.interface, timeout=0.7, retry=0)
        for _, packet in answers:
            if packet[ARP].hwsrc.lower().startswith(OUI):
                found[packet[ARP].psrc] = packet[ARP].hwsrc.lower()
    worker.join(timeout=max(args.seconds, 0) + 1)
    # An HMI with an address outside the requested range is reported only if it is
    # directly visible on the selected link and its MAC matches the IDEC prefix.
    for _, packet in observed:
        if ARP in packet and packet[ARP].hwsrc.lower().startswith(OUI):
            found.setdefault(packet[ARP].psrc, packet[ARP].hwsrc.lower())
    confirmed = {}
    for ip, mac in sorted(found.items(), key=lambda item: ipaddress.ip_address(item[0])):
        try:
            with socket.create_connection((ip, 2537), timeout=0.6):
                confirmed[ip] = mac
        except OSError:
            print(f'IDEC MAC {mac} at {ip}; port 2537 unreachable (check PC route)')
    if not confirmed:
        print(f'No HMI found in {network} on {args.interface}')
        return 1
    wanted = {ip: set() for ip in confirmed}
    for _, packet in observed:
        if ARP not in packet or packet[ARP].op != 1:
            continue
        source = packet[ARP].psrc
        if source in confirmed and packet[ARP].hwsrc.lower() == confirmed[source]:
            target = packet[ARP].pdst
            if target != source and ipaddress.ip_address(target).is_private:
                wanted[source].add(target)
    for ip in confirmed:
        requests = sorted(wanted[ip], key=ipaddress.ip_address)
        if requests:
            print(f'HMI found {ip} requesting: {", ".join(requests)}')
        else:
            print(f'HMI found {ip} not requesting devices during {args.seconds:g}s')
    addresses = sorted(set().union(*wanted.values()), key=ipaddress.ip_address)
    if not addresses:
        return 0
    if args.no_prompt or input('Configure temporary fake PLC address(es) and serve? [y/N] ').lower() != 'y':
        return 0
    added = []
    try:
        for address in addresses:
            # Use /32 to avoid disturbing the existing routes and primary addresses.
            prefix = 32
            command = alias_command(args.interface, address, prefix, True)
            print('Running:', ' '.join(command))
            subprocess.run(command, check=True)
            added.append((address, prefix))
        print('Stop with Ctrl-C. Temporary addresses are removed on clean exit.')
        serve(addresses)
    except KeyboardInterrupt:
        pass
    finally:
        for address, prefix in reversed(added):
            subprocess.run(alias_command(args.interface, address, prefix, False), check=False)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        sys.exit(2)
