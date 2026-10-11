#!/bin/bash
df -h
printf '\nEnter USB mount directory: '
read -r USB

(
    if [ -z "$USB" ] || [ ! -d "$USB" ]; then
        echo "USB directory does not exist."
        exit 1
    fi

    OUT="$USB/hg2j-7u_software_support.txt"

    inventory()
    {
        printf '\n===== %s =====\n' "$1"
    }

    {
        inventory "HG2J-7U SOFTWARE SUPPORT INVENTORY"
        date
        uname -a
        cat /etc/os-release /etc/issue 2>/dev/null

        inventory "STORAGE AND MOUNTS"
        df -h
        cat /proc/mounts

        inventory "CPU AND MEMORY"
        cat /proc/cpuinfo
        cat /proc/meminfo

        inventory "COMMAND SEARCH PATH"
        printf '%s\n' "$PATH"

        inventory "BUSYBOX BUILT-IN COMMANDS"
        busybox 2>&1
        busybox --list 2>/dev/null

        inventory "EXECUTABLE FILES AND EXECUTABLE SYMLINKS"
        for DIR in /bin /sbin /usr/bin /usr/sbin /usr/libexec \
                   /usr/local /opt /home
        do
            [ -d "$DIR" ] || continue
            find "$DIR" \( -type f -o -type l \) 2>/dev/null
        done |
        sort -u |
        while IFS= read -r FILE
        do
            [ -x "$FILE" ] && ls -ld "$FILE"
        done

        inventory "SHARED LIBRARIES AND LOADERS"
        for DIR in /lib /usr/lib /usr/local/lib
        do
            [ -d "$DIR" ] || continue
            find "$DIR" \( -name '*.so*' -o -name 'ld-*' \) \
                -exec ls -ld {} \; 2>/dev/null
        done

        inventory "GRAPHICS, IMAGE, MEDIA AND GUI SUPPORT FILES"
        for DIR in /lib /usr /opt /etc /home
        do
            [ -d "$DIR" ] || continue
            find "$DIR" \( -type f -o -type l \) 2>/dev/null
        done |
        awk '
        {
            name = tolower($0)
            if (name ~ /weston|wayland|xorg|x11|egl|gles|libgl[.-]|drm|gbm/ ||
                name ~ /gstreamer|gst-|libgst|ffmpeg|ffplay|avcodec|avformat/ ||
                name ~ /mplayer|mpv|vlc|codec|v4l|video|jpeg|png|tiff|webp/ ||
                name ~ /pixbuf|cairo|pango|freetype|fontconfig|sdl|gtk|qt/ ||
                name ~ /alsa|asound|pulse|audio|aplay|image|viewer|qml/)
                print
        }' |
        sort -u

        inventory "PACKAGE DATABASE SUMMARIES"
        for FILE in /var/lib/opkg/status /usr/lib/opkg/status \
                    /var/lib/dpkg/status
        do
            [ -f "$FILE" ] || continue
            printf '\n--- %s ---\n' "$FILE"
            awk '/^(Package|Version|Architecture|Status|Description):/' "$FILE"
        done

        inventory "DISPLAY AND SESSION SETTINGS"
        printf 'DISPLAY=%s\n' "$DISPLAY"
        printf 'WAYLAND_DISPLAY=%s\n' "$WAYLAND_DISPLAY"
        printf 'XDG_RUNTIME_DIR=%s\n' "$XDG_RUNTIME_DIR"
        ps

        inventory "GRAPHICS, SOUND, INPUT AND USB DEVICE NODES"
        for DIR in /dev/dri /dev/input /dev/snd /dev/bus/usb
        do
            [ -d "$DIR" ] && ls -lR "$DIR"
        done
        ls -l /dev/fb* /dev/video* /dev/ttyACM* /dev/ttyUSB* 2>/dev/null

        inventory "INPUT DEVICE DETAILS"
        cat /proc/bus/input/devices 2>/dev/null

        inventory "KERNEL MODULES"
        cat /proc/modules 2>/dev/null
        find /lib/modules -type f 2>/dev/null | sort

        inventory "SHARED DATA DIRECTORIES"
        ls -l /usr/share /usr/local/share 2>/dev/null

        inventory "STARTUP SERVICES"
        ls -l /etc/init.d /etc/rc*.d 2>/dev/null

        inventory "END OF INVENTORY"
    } > "$OUT" 2>&1

    sync
    printf '\nSaved: %s\n' "$OUT"
    ls -lh "$OUT"
)
