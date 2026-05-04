#!/bin/bash
echo "Temporarily setting Ethernet to 192.168.1.X via dchp"
sudo ip link set enp2s0 down
sudo ip addr flush dev enp2s0 
sudo ip addr add 192.168.1.10/24 dev enp2s0
sudo ip link set enp2s0 up
sudo dhclient enp2s0 
ifconfig enp2s0  | grep 'inet' | cut -d: -f2 | awk '{print $2}'
