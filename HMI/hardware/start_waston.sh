#!/bin/bash
# get the weston terminal running.
XDG_RUNTIME_DIR=/tmp/0-runtime-dir \
WAYLAND_DISPLAY=wayland-0 \
weston-terminal >/tmp/weston-terminal.log 2>&1 &
