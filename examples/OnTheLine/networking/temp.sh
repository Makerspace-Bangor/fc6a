#!/bin/bash
set -e
IFACE=enp2s0

echo "Temporarily setting Ethernet to 192.168.1.10"

sudo dhclient -r "$IFACE" || true
sudo ip addr flush dev "$IFACE"
sudo ip link set "$IFACE" up
sudo ip addr add 192.168.1.10/24 dev "$IFACE"

ifconfig enp2s0  | grep 'inet' | cut -d: -f2 | awk '{print $2}'
