#!/bin/bash
#
# HG2J IDEC Runtime - Docker Test Environment
# Runs original ARM32 HG2J userspace under QEMU on Linux Mint.
#
# Current objective:
# Investigate idec_init.BIN startup and its shutdown loop.
#
# Docker based on image of HMI 

set -e

IMAGE="hg2j-runtime"
CONTAINER="hg2j-lab"

# Remove previous test container.
docker rm -f "$CONTAINER" 2>/dev/null || true

# Start original IDEC initializer.
docker run -d \
    --name "$CONTAINER" \
    --platform linux/arm/v7 \
    --mount type=bind,src="$(pwd)/runtime-rom",dst=/home/idec/rom \
    --network none \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --shm-size=64m \
    --tmpfs /var/volatile:rw,mode=755,size=50m \
    --tmpfs /home/idec/.tmp:rw,exec,mode=1777,size=20m \
    --tmpfs /home/idec/.work:rw,mode=1777,size=10m \
    --tmpfs /home/idec/usr/tmp:rw,mode=1777,size=100m \
    -e QEMU_CPU=cortex-a8 \
    -e QEMU_STRACE=1 \
    -e XDG_CONFIG_HOME=/etc \
    -e XDG_RUNTIME_DIR=/tmp/0-runtime-dir \
    -e WAYLAND_DISPLAY=wayland-0 \
    --entrypoint /bin/sh \
    "$IMAGE" \
    -c '
        set -e

        mkdir -p /var/volatile/tmp
        chmod 1777 /var/volatile/tmp

        mkdir -p /var/volatile/tmp/0-runtime-dir
        chmod 777 /var/volatile/tmp/0-runtime-dir

        touch /var/volatile/tmp/0-runtime-dir/wayland-0.lock
        chmod 777 /var/volatile/tmp/0-runtime-dir/wayland-0.lock

        mkdir -p /home/idec/.work/ftp_srv

        ls -ld /tmp /var/tmp /var/volatile/tmp/0-runtime-dir
        ls -l /tmp/0-runtime-dir/wayland-0.lock
 
        mkdir -p /dev/dri
        touch /dev/dri/card0
        chmod 666 /dev/dri/card0

        mkdir -p /dev
        touch /dev/mtdblock0
        chmod 666 /dev/mtdblock0
 
        exec /home/root/idec_init.BIN
    '

echo
echo "Container: $CONTAINER"
echo "Image:     $IMAGE"
echo
echo "Inspect with:"
echo "  docker ps --filter name=$CONTAINER"
echo "  docker logs --tail 50 $CONTAINER"
echo "  docker exec $CONTAINER ps"
