# 1 2 1 2, check check
<pre>
arm-linux-gnueabihf-gcc -O2 -static -s -Wall -Wextra -o hg2j_screen_scpi_arm hg2j_screen_scpi.c


scp -O -o HostKeyAlgorithms=+ssh-rsa hg2j_screen_scpi_arm service@192.168.1.20:/home/service/
service@192.168.1.20's password: 
hg2j_screen_scpi_arm                          100%  353KB   1.4MB/s   00:00  

# ya thought you were going to run:
./hg2j_screen_scpi_arm 192.168.1.20 0 /dev/usbtmc0
but that device did not enumerate.
no dmesg, no lsusb 
so we do this cheesey little hack:

ls /dev/* > plugged
ls /dev/* > unplugged
diff plugged unplugged 

--- plugged
+++ unplugged
@@ -180,7 +180,6 @@
 13:65
 189:0
 189:128
-189:129
 226:0
 226:1
 226:128
root@am335x-idec-pd:/home/service# for f in idVendor idProduct manufacturer product busnum devnum; do
>     printf "%-15s " "$f"
>     cat "/sys/bus/usb/devices/2-1/$f"
> done
idVendor        0957
idProduct       0407
manufacturer    Agilent Technologies
product         33220A Waveform Generator
busnum          2
devnum          3


root@am335x-idec-pd:/home/service# ./hg2j_usbtmc_idn_arm /dev/bus/usb/002/003
USB identity: 0957:0407
Claimed interface 0, bulk OUT 0x02, bulk IN 0x86
USBTMC DEV_DEP_MSG_OUT sent, tag=1: *IDN?
USBTMC response: 66 bytes, msg=2, tag=2, payload=54, EOM=1
33220A identification: Agilent Technologies,33220A,MY44009632,2.07-2.00-22-2


</pre>
