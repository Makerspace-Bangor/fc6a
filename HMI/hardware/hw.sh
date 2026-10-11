#!/bin/bash
# Collect a read-only hardware and system inventory from an IDEC HMI.
# The report is written to the mounted USB drive at the path below.

set -u

REPORT_DIR=/home/idec/usr/exmem/A
REPORT_FILE=$REPORT_DIR/hg2j-7u_hardware.txt
TMP_FILE=$REPORT_FILE.tmp.$$

if [ ! -d "$REPORT_DIR" ]; then
    echo "Error: $REPORT_DIR does not exist." >&2
    exit 1
fi

# Do not accidentally write the report to the HMI's internal filesystem if the
# USB drive is not mounted at the expected location.
if ! awk -v path="$REPORT_DIR" '$2 == path { found=1 } END { exit !found }' \
    /proc/mounts; then
    echo "Error: $REPORT_DIR is not a mounted filesystem. Mount the USB drive first." >&2
    exit 1
fi

umask 022
trap 'rm -f "$TMP_FILE"' EXIT HUP INT TERM

{
    printf '%s\n' 'HG2J-7U HMI HARDWARE INVENTORY'
    printf '%s\n' '================================'
    printf 'Generated: %s\n' "$(date 2>/dev/null || echo unknown)"
    printf 'Host name: %s\n' "$(hostname 2>/dev/null || echo unknown)"
    printf '\n'

    section() {
        printf '\n--- %s ---\n' "$1"
    }

    show_file() {
        if [ -r "$1" ]; then
            printf '\n[%s]\n' "$1"
            cat "$1" 2>&1
        else
            printf '\n[%s unavailable]\n' "$1"
        fi
    }

    section 'Operating system and kernel'
    uname -a 2>&1 || true
    show_file /etc/os-release
    show_file /etc/version
    show_file /proc/version

    section 'Device model and device tree'
    for f in /proc/device-tree/model /sys/firmware/devicetree/base/model; do
        if [ -r "$f" ]; then
            printf '%s: ' "$f"
            tr '\000' '\n' < "$f" 2>/dev/null
        fi
    done
    show_file /proc/cmdline

    section 'Processor'
    show_file /proc/cpuinfo
    for f in /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq \
             /sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_min_freq \
             /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq; do
        if [ -r "$f" ]; then
            printf '%s: ' "$f"
            cat "$f"
        fi
    done
    if command -v lscpu >/dev/null 2>&1; then
        printf '\n[lscpu]\n'
        lscpu 2>&1 || true
    fi

    section 'Memory'
    show_file /proc/meminfo
    if command -v free >/dev/null 2>&1; then
        printf '\n[free -h]\n'
        free -h 2>&1 || free 2>&1 || true
    fi

    section 'Flash, block devices, and partitions'
    show_file /proc/mtd
    show_file /proc/partitions
    show_file /proc/scsi/scsi
    for d in /sys/class/block/*; do
        [ -e "$d" ] || continue
        name=${d##*/}
        printf '\nDevice: %s\n' "$name"
        for attr in dev size removable ro device/model device/vendor device/serial; do
            f=$d/$attr
            if [ -r "$f" ]; then
                printf '  %s: ' "$attr"
                cat "$f" 2>/dev/null
            fi
        done
        if [ -r "$d/uevent" ]; then
            sed 's/^/  /' "$d/uevent" 2>/dev/null
        fi
    done
    for d in /sys/class/mtd/mtd*; do
        [ -e "$d" ] || continue
        printf '\nMTD device: %s\n' "${d##*/}"
        for attr in name type size erasesize flags; do
            f=$d/$attr
            if [ -r "$f" ]; then
                printf '  %s: ' "$attr"
                cat "$f" 2>/dev/null
            fi
        done
    done
    if command -v lsblk >/dev/null 2>&1; then
        printf '\n[lsblk]\n'
        lsblk 2>&1 || true
    fi
    if command -v blkid >/dev/null 2>&1; then
        printf '\n[blkid]\n'
        blkid 2>&1 || true
    fi

    section 'Mounted filesystems and disk usage'
    if command -v df >/dev/null 2>&1; then
        df -h 2>&1 || df 2>&1 || true
    fi
    show_file /proc/mounts

    section 'USB devices'
    found_usb=0
    for d in /sys/bus/usb/devices/*; do
        [ -d "$d" ] || continue
        [ -r "$d/idVendor" ] || continue
        found_usb=1
        printf '\nUSB device: %s\n' "${d##*/}"
        for attr in idVendor idProduct bcdDevice manufacturer product serial; do
            f=$d/$attr
            if [ -r "$f" ]; then
                printf '  %s: ' "$attr"
                cat "$f" 2>/dev/null
            fi
        done
    done
    [ "$found_usb" -eq 1 ] || echo 'No USB device entries found in sysfs.'
    if command -v lsusb >/dev/null 2>&1; then
        printf '\n[lsusb]\n'
        lsusb 2>&1 || true
    fi

    section 'Network interfaces'
    for f in /sys/class/net/*; do
        [ -e "$f" ] || continue
        name=${f##*/}
        printf '\nInterface: %s\n' "$name"
        for attr in address type operstate mtu; do
            if [ -r "$f/$attr" ]; then
                printf '  %s: ' "$attr"
                cat "$f/$attr" 2>/dev/null
            fi
        done
    done
    if command -v ip >/dev/null 2>&1; then
        printf '\n[ip address]\n'
        ip address 2>&1 || true
    elif command -v ifconfig >/dev/null 2>&1; then
        printf '\n[ifconfig -a]\n'
        ifconfig -a 2>&1 || true
    fi

    section 'Thermal sensors'
    for f in /sys/class/thermal/thermal_zone*/type \
             /sys/class/thermal/thermal_zone*/temp \
             /sys/class/hwmon/hwmon*/name \
             /sys/class/hwmon/hwmon*/temp*_input; do
        [ -r "$f" ] || continue
        printf '%s: ' "$f"
        cat "$f" 2>/dev/null
    done

    section 'Relevant boot messages'
    if command -v dmesg >/dev/null 2>&1; then
        dmesg 2>&1 | grep -Ei 'am33|cpu|memory|ram|mtd|ubi|nand|flash|mmc|sd[a-z]|usb|ethernet|phy|thermal' \
            | tail -n 160 || true
    else
        echo 'dmesg command unavailable.'
    fi

echo
echo "=== Display and touchscreen ==="
for f in /proc/fb \
         /sys/class/graphics/fb*/name \
         /sys/class/graphics/fb*/virtual_size \
         /sys/class/graphics/fb*/bits_per_pixel \
         /sys/class/graphics/fb*/modes \
         /sys/class/drm/card*-*/modes \
         /sys/class/backlight/*/brightness \
         /sys/class/backlight/*/max_brightness; do
    [ -r "$f" ] || continue
    echo "$f:"
    cat "$f"
done

echo
echo "=== Input devices ==="
cat /proc/bus/input/devices


if [ -r /proc/bus/input/devices ]; then
    echo
    echo "=== Input devices (includes touchscreen, if detected) ==="
    cat /proc/bus/input/devices
    printf '\n%s\n' 'End of inventory.'
} > "$TMP_FILE" 2>&1

if mv "$TMP_FILE" "$REPORT_FILE"; then
    trap - EXIT HUP INT TERM
    echo "Hardware inventory written to: $REPORT_FILE"
else
    echo "Error: could not write report to $REPORT_FILE" >&2
    exit 1
fi

