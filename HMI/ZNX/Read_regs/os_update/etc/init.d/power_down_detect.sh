#!/bin/sh
modprobe power_down_detect
chmod 666 /dev/pwdu0
chmod 666 /sys/devices/platform/power_down_detect/power_down_detect_status
