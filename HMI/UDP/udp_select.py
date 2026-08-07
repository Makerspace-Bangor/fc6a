#!/usr/bin/env python3

import re
import socket
from typing import Optional

"""
Not a fork, but going to use the concept. 
https://github.com/mitchsowa/edgerouter-plc-mux

in conjuction with N-Units ID'd by N-Unit+1 = IP
and work previously done, to translate PLC traffic to the HMI
via a PC direct connection, or over a network,
we should be able to process selected Units specificly, 
without the need for additional hardware.

it should be possbile to then extend the number of units to control 
well beyond 4
"""

LISTEN_IP = "0.0.0.0"
LISTEN_PORT = 5150

# Set this to the HMI IP to reject packets from other devices.
# Leave it as None to accept packets from any address.
HMI_IP = None

# Change these addresses to match the actual PLCs.
# Using N+1 = ip
PLC_BY_SELECTOR = {
    1: "192.168.1.2",
    2: "192.168.1.3",
    3: "192.168.1.4",
    4: "192.168.1.5",
    5: "192.168.1.6",
    6: "192.168.1.7",
    7: "192.168.1.8",
    8: "192.168.1.9",
    9: "192.168.1.10",
}

# The referenced HMI sends 0 during startup.
DEFAULT_SELECTOR = 1

# The original router service replies "ok N".
# Leave disabled unless the HMI requires a response.
SEND_ACK = False


def decode_selector(packet: bytes) -> Optional[int]:
    """
    Decode either:

        ASCII: b"1", b"2\\r\\n", b"PLC=3"
        Binary: b"\\x01", b"\\x02", b"\\x03"

    Returns None for an empty packet.
    """

    if not packet:
        return None

    # Match the behavior of the original project: use the first ASCII digit.
    match = re.search(rb"[0-9]", packet)

    if match:
        return int(match.group(0))

    # Otherwise interpret the first byte as the selector.
    return packet[0]


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind((LISTEN_IP, LISTEN_PORT))

    active_selector = None
    active_plc_ip = None

    #print(f"Listening for HMI selection packets on UDP {LISTEN_PORT}")

    while True:
        packet, sender = sock.recvfrom(2048)
        sender_ip, sender_port = sender

        if HMI_IP is not None and sender_ip != HMI_IP:
            continue

        selector = decode_selector(packet)

        if selector is None:
            print("Ignored empty UDP packet")
            continue

        # Preserve the original project's startup behavior.
        requested_selector = (
            DEFAULT_SELECTOR if selector == 0 else selector
        )

        plc_ip = PLC_BY_SELECTOR.get(requested_selector)

        if plc_ip is None:
            print(f"Ignored unknown selector: {selector}")

            if SEND_ACK:
                sock.sendto(b"err", sender)

            continue

        if (
            requested_selector != active_selector
            or plc_ip != active_plc_ip
        ):
            active_selector = requested_selector
            active_plc_ip = plc_ip
            print(active_selector)
            #selection_changed(active_selector, active_plc_ip)
	    # Only update on selection change
            #print(
            #    f"UDP from {sender_ip}:{sender_port}  "
            #    f"data={packet!r}  hex={packet.hex(' ')}"
            #)


        if SEND_ACK:
            reply = f"ok {active_selector}".encode("ascii")
            sock.sendto(reply, sender)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped")

"""
:~/fc6a/HMI/UDP$ python3 udp_select.py 
Listening for HMI selection packets on UDP 5150
Selected PLC 2: 192.168.1.3
UDP from 192.168.1.150:49274  data=b'2'  hex=32
Selected PLC 3: 192.168.1.4
UDP from 192.168.1.150:49274  data=b'3'  hex=33
	
"""	
	
