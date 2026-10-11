# MF HG2J-7U SSH SON!

# System Specs:
<pre>
service@am335x-idec-pd:~$ cat /etc/os-release
ID="arago"
NAME="Arago"
VERSION="2019.07"
VERSION_ID="2019.07"
PRETTY_NAME="Arago 2019.07"

service@am335x-idec-pd:~$ uname -a
Linux am335x-idec-pd 4.19.59-idec-hg2j-001.001.000.000-g5f8c1c6121 #1 PREEMPT Fri Nov 29 01:11:25 UTC 2024 armv7l GNU/Linux

service@am335x-idec-pd:~$ cat /proc/cpuinfo
processor	: 0
model name	: ARMv7 Processor rev 2 (v7l)
BogoMIPS	: 597.60
Features	: half thumb fastmult vfp edsp neon vfpv3 tls vfpd32 
CPU implementer	: 0x41
CPU architecture: 7
CPU variant	: 0x3
CPU part	: 0xc08
CPU revision	: 2

Hardware	: Generic AM33XX (Flattened Device Tree)
Revision	: 0000
Serial		: 00:03:7b:20:24:4f
service@am335x-idec-pd:~$ uname -a
Linux am335x-idec-pd 4.19.59-idec-hg2j-001.001.000.000-g5f8c1c6121 #1 PREEMPT Fri Nov 29 01:11:25 UTC 2024 armv7l GNU/Linux

service@am335x-idec-pd:~$ free -h
             total       used       free     shared    buffers     cached
Mem:        248564      61428     187136       6668        128      21280
-/+ buffers/cache:      40020     208544
Swap:            0          0          0

service@am335x-idec-pd:~$ df -h
Filesystem                Size      Used Available Use% Mounted on
ubi0:rootfs-a           129.7M     50.3M     74.7M  40% /
devtmpfs                 96.9M      8.0K     96.9M   0% /dev
tmpfs                   121.4M     68.0K    121.3M   0% /run
tmpfs                    50.0M      1.5M     48.5M   3% /var/volatile
tmpfs                    20.0M      2.4M     17.6M  12% /home/idec/.tmp
tmpfs                    10.0M      4.0K     10.0M   0% /home/idec/.work
tmpfs                   100.0M         0    100.0M   0% /home/idec/usr/tmp
/dev/mtdblock16          39.7M     28.0M     11.7M  71% /home/idec/rom
/dev/mtdblock17           2.0M    764.0K      1.2M  38% /mnt/work

service@am335x-idec-pd:~$ df -i
df: invalid option -- 'i'
BusyBox v1.29.3 (2021-11-11 06:46:22 UTC) multi-call binary.

Usage: df [-PkmhT] [FILESYSTEM]...

service@am335x-idec-pd:~$ df -h /
Filesystem                Size      Used Available Use% Mounted on
ubi0:rootfs-a           129.7M     50.3M     74.7M  40% /

service@am335x-idec-pd:~$ dmesg 
dmesg: klogctl: Function not implemented

service@am335x-idec-pd:~$ env
USER=service
SSH_CLIENT=192.168.1.160 42110 22
SHLVL=1
HOME=/home/service
SSH_TTY=/dev/ttyp0
PS1=\u@\h:\w\$ 
WAYLAND_DISPLAY=wayland-0
LOGNAME=service
TERM=xterm-256color
PATH=/usr/local/bin:/usr/bin:/bin
WS_CALUDEV_FILE=/etc/udev/rules.d/ws-calibrate.rules
XDG_RUNTIME_DIR=/tmp/0-runtime-dir
XDG_CONFIG_HOME=/etc/
SHELL=/bin/sh
PWD=/home/service
SSH_CONNECTION=192.168.1.160 42110 192.168.1.20 22
EDITOR=vi



</pre>


## Software:
- extract_znx.py  extracts a ZNX into the compressed linux archive and the HMI program code
- repak_znx_roundtrip.py: produces a ZNX file, and compares it to its original source 
- hmi_znx_download.py downloads a ZNX file to your HMI




# Method:
Extract a functional ZNX binary, edit the linux components to add a user named service.
edit the dropbear ssh config. 
recompress the os files, and znv program.
download 


# login to service account: 
  - direct connection: add ip: sudo ip addr add 192.168.1.160/24 dev enp2s0

  - ssh -o IdentitiesOnly=yes -o HostKeyAlgorithms=+ssh-rsa service@192.168.1.20


# OG SRC:
<a href="files/rr_ssh.ZNX"> user: service pass: avilable upon request</a>

Alternatively: extract the rr_ssh.ZNX, 
run $openssl passwd -6  
to create your own password,  
go into etc/shadow, and populate the serivce user with your own password hash. 


then repack the os, and download your ssh enabled hmi.






















