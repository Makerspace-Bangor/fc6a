#!/bin/sh
### BEGIN INIT INFO
# Provides:          bootmisc
# Required-Start:    $local_fs mountvirtfs
# Required-Stop:     $local_fs
# Default-Start:     S
# Default-Stop:      0 6
# Short-Description: Misc and other.
### END INIT INFO

if [ -e /proc/cpu/alignment ]; then
   echo "3" > /proc/cpu/alignment
fi

/etc/init.d/hwclock.sh start

mkdir -p "/var/volatile/log"
mkdir -p "/var/run/wpa_supplicant"
mkdir -p "/run/lock"
hostname "am335x-idec-pd"
: exit 0
