<pre>
# here, we fail
 * sn@ker:~/fc6a/HMI/selfTest$ gcc -O2 -Wall -Wextra -o hg2j_self_register_pc hg2j_self_register.c
 * sn@ker:~/fc6a/HMI/selfTest$ ./hg2j_self_register_pc 192.168.1.20 5
 * Connecting to 192.168.1.20:2537 ...
 * TCP connected; registering LSD31 with CG01
 * CG was not ACKed (expected inner 06)
 * Reply (26 bytes), inner bytes: 15 30 30 46 46 30 33 0D
 * NAK 00FF03 CR
 * Which is a FAIL, but its a Maintenance Protocol Fail. :D

# after Authentication, we succeed!
sn@ker:~/fc6a/HMI/selfTest$ ./hg2j_self_register_pc 192.168.1.20 5
Connecting to 192.168.1.20:2537 ...
TCP connected; registering LSD31 with CG01
CG accepted; touch/change NV4 screens while polling:
01  LSD31 = 2 (0x0002)
02  LSD31 = 2 (0x0002)
03  LSD31 = 2 (0x0002)
04  LSD31 = 2 (0x0002)
05  LSD31 = 2 (0x0002)

so ugh. we can read the registers from my PC, whoopdee doo.
now to cross compile, and try it over on the hmi!

arm-linux-gnueabihf-gcc -O2 -static -s -o hg2j_self_register_arm hg2j_self_register.c

sn@ker:~/fc6a/HMI/selfTest$ scp -O -o HostKeyAlgorithms=+ssh-rsa -o IdentitiesOnly=yes hg2j_self_register_arm service@192.168.1.20:/home/service/
hg2j_self_register_arm                        100%  353KB   1.7MB/s   00:00  

root@am335x-idec-pd:/home/service# ./hg2j_self_register_arm 
Connecting to 127.0.0.1:2537 ...
connect: Connection refused
---ugh ok...

root@am335x-idec-pd:/home/service# ./hg2j_self_register_arm 192.168.1.20 5
Connecting to 192.168.1.20:2537 ...
TCP connected; registering LSD31 with CG01
CG accepted; touch/change NV4 screens while polling:
01  LSD31 = 2 (0x0002)
02  LSD31 = 2 (0x0002)
03  LSD31 = 2 (0x0002)
04  LSD31 = 2 (0x0002)
05  LSD31 = 2 (0x0002)
root@am335x-idec-pd:/home/service# 
__# BOOYAH!
This confirms we can read registers from the hmi's own ip. not localhost, even thought it is listening there...

</pre>
