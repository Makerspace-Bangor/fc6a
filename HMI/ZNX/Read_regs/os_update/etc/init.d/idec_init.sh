#!/bin/sh
export XDG_CONFIG_HOME=/etc/
export XDG_RUNTIME_DIR=/tmp/0-runtime-dir
export WAYLAND_DISPLAY=wayland-0
export WS_CALUDEV_FILE=/etc/udev/rules.d/ws-calibrate.rules

# isolate the wlan and lan of linux
echo 1 > /proc/sys/net/ipv4/conf/all/arp_ignore
echo 2 > /proc/sys/net/ipv4/conf/all/arp_announce

# start the idec_init.BIN
/home/root/idec_init.BIN &
