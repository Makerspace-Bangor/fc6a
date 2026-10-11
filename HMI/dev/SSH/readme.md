# MF HG2J-7U SSH SON!

# System Specs:
<pre>
service@am335x-idec-pd:~$ cat /etc/os-release
ID="arago"
NAME="Arago"
VERSION="2019.07"
VERSION_ID="2019.07"
PRETTY_NAME="Arago 2019.07"

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

service@am335x-idec-pd:~$ cat /proc/partitions
major minor  #blocks  name

   1        0      65536 ram0
   1        1      65536 ram1
   1        2      65536 ram2
   1        3      65536 ram3
  31        0        128 mtdblock0
  31        1        128 mtdblock1
  31        2        128 mtdblock2
  31        3        128 mtdblock3
  31        4        128 mtdblock4
  31        5        256 mtdblock5
  31        6       1024 mtdblock6
  31        7        128 mtdblock7
  31        8        128 mtdblock8
  31        9       8192 mtdblock9
  31       10        256 mtdblock10
  31       11      48128 mtdblock11
  31       12       8192 mtdblock12
  31       13        256 mtdblock13
  31       14        256 mtdblock14
  31       15     151552 mtdblock15
  31       16      40960 mtdblock16
  31       17       2048 mtdblock17

service@am335x-idec-pd:~$ cat /proc/meminfo
MemTotal:         248564 kB
MemFree:          187136 kB
MemAvailable:     197836 kB
Buffers:             128 kB
Cached:            21280 kB
SwapCached:            0 kB
Active:            13576 kB
Inactive:          15956 kB
Active(anon):       8232 kB
Inactive(anon):     6560 kB
Active(file):       5344 kB
Inactive(file):     9396 kB
Unevictable:           0 kB
Mlocked:               0 kB
HighTotal:             0 kB
HighFree:              0 kB
LowTotal:         248564 kB
LowFree:          187136 kB
SwapTotal:             0 kB
SwapFree:              0 kB
Dirty:                 4 kB
Writeback:             0 kB
AnonPages:          8136 kB
Mapped:            25056 kB
Shmem:              6668 kB
Slab:               7636 kB
SReclaimable:       2216 kB
SUnreclaim:         5420 kB
KernelStack:         736 kB
PageTables:          564 kB
NFS_Unstable:          0 kB
Bounce:                0 kB
WritebackTmp:          0 kB
CommitLimit:      124280 kB
Committed_AS:     350768 kB
VmallocTotal:     770048 kB
VmallocUsed:           0 kB
VmallocChunk:          0 kB
Percpu:               32 kB
CmaTotal:          49152 kB
CmaFree:           42868 kB

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


# OG SRC:
<a href="files/rr_ssh.ZNX"> user: service pass: avilable upon request</a>

an alt on that: extract the os files, 
run $openssl passwd -6
to create your own password,
go into etc/shadow, and populate the serivce user with your own password hash. 


then repack the os, and download your ssh enabled hmi.






















