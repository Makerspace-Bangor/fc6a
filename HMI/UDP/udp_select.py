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
PLC_BY_SELECTOR = {
    1: "192.168.1.2",
    2: "192.168.1.3",
    3: "192.168.1.4",
    4: "192.168.1.5",
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


def selection_changed(selector: int, plc_ip: str) -> None:
    """
    This function runs only when the selected PLC changes.

    Put the selected PLC into your other program here.
    """

    print(f"Selected PLC {selector}: {plc_ip}")

    # Example:
    # plc_manager.select(plc_ip)
    # Or:
    # plc = MiSmTCP(plc_ip, device="FF", timeout=2.0)


def main() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    sock.bind((LISTEN_IP, LISTEN_PORT))

    active_selector = None
    active_plc_ip = None

    print(f"Listening for HMI selection packets on UDP {LISTEN_PORT}")

    while True:
        packet, sender = sock.recvfrom(2048)
        sender_ip, sender_port = sender

        if HMI_IP is not None and sender_ip != HMI_IP:
            continue

        selector = decode_selector(packet)

        print(
            f"UDP from {sender_ip}:{sender_port}  "
            f"data={packet!r}  hex={packet.hex(' ')}"
        )

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

            selection_changed(active_selector, active_plc_ip)
        else:
            print(
                f"PLC {active_selector} remains selected: "
                f"{active_plc_ip}"
            )

        if SEND_ACK:
            reply = f"ok {active_selector}".encode("ascii")
            sock.sendto(reply, sender)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped")
