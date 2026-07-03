<pre>
Scan taken from when the Firmware was downloading 
$ nmap -Pn -p100-65535 192.168.1.20
Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-07-02 20:38 EDT
Nmap scan report for 192.168.1.20
Host is up (0.0022s latency).
Not shown: 65433 closed tcp ports (conn-refused)
PORT     STATE SERVICE
2537/tcp open  upgrade
2539/tcp open  vsiadmin
2541/tcp open  lonworks2

$ md5sum os_update.znx
4d2f97f9693b4d164ee04ff6d5568cf3  os_update.znx

$ cat os_update.znx.md5 
4d2f97f9693b4d164ee04ff6d5568cf3  9087f2bc-0a9a-4fa3-b801-8f4dc9fa723d.znx

$ file -i os_update.znx
os_update.znx: application/octet-stream; charset=binary

$ hexdump -C os_update.znx | head
00000000  5a 4e 58 00 01 00 00 00  01 00 02 00 00 00 00 00  |ZNX.............|
00000010  03 00 02 00 00 00 00 00  f8 3e 98 02 01 00 00 00  |.........>......|
00000020  48 00 00 00 7c b5 6b 02  a6 91 2c c0 14 00 00 00  |H...|.k...,.....|
00000030  6f 73 5f 75 70 64 61 74  65 2e 74 61 72 2e 78 7a  |os_update.tar.xz|
00000040  00 00 00 00 02 00 00 00  c4 b5 6b 02 34 89 2c 00  |..........k.4.,.|
00000050  2e c4 36 55 0c 00 00 00  70 72 6f 6a 65 63 74 2e  |..6U....project.|
00000060  7a 6e 76 00 fd 37 7a 58  5a 00 00 01 69 22 de 36  |znv..7zXZ...i".6|
00000070  04 c0 b0 b3 f2 03 80 80  80 06 21 01 14 00 00 00  |..........!.....|
00000080  7b 13 8e 21 e2 27 10 ef  ff 5d 00 17 0b bc 1c 7d  |{..!.'...].....}|
00000090  01 95 c0 1d 3f 82 a2 8a  c4 9e 8d 2f 6a 08 0f 13  |....?....../j...|

# make a disk image 
$ dd if=os_update.znx of=os_update.tar.xz bs=1 skip=$((0x64))

# extract the os_update.tar.xz listed in head
$tar -tf os_update.tar.xz

...>> see untar.txt
file corupt. ok well try something else.
## Here, a clean ZNX from standard NV4 output
$ hexdump -C Read_regs.ZNX | head
00000000  5a 4e 58 00 01 00 00 00  01 00 02 00 00 00 00 00  |ZNX.............|
00000010  03 00 02 00 00 00 00 00  f8 3e 98 02 01 00 00 00  |.........>......|
00000020  48 00 00 00 7c b5 6b 02  a6 91 2c c0 14 00 00 00  |H...|.k...,.....|
00000030  6f 73 5f 75 70 64 61 74  65 2e 74 61 72 2e 78 7a  |os_update.tar.xz|
00000040  00 00 00 00 02 00 00 00  c4 b5 6b 02 34 89 2c 00  |..........k.4.,.|
00000050  2e c4 36 55 0c 00 00 00  70 72 6f 6a 65 63 74 2e  |..6U....project.|
00000060  7a 6e 76 00 fd 37 7a 58  5a 00 00 01 69 22 de 36  |znv..7zXZ...i".6|
00000070  04 c0 b0 b3 f2 03 80 80  80 06 21 01 14 00 00 00  |..........!.....|
00000080  7b 13 8e 21 e2 27 10 ef  ff 5d 00 17 0b bc 1c 7d  |{..!.'...].....}|
00000090  01 95 c0 1d 3f 82 a2 8a  c4 9e 8d 2f 6a 08 0f 13  |....?....../j...|

But Im thinking that the end of the tar.xz file must be in the znx file, 
bundled with the program code. 
I suspect that they are separate even if they are part of the same ZNX file.
head eludes to this, with project.znv, and os_update.tar.xz
maybe I can use scalple to pull the xz, znv files from thier embeded offsets.
or i could do math...

0x48 + 0x1c = 0x64              start of os_update.tar.xz
0x026bb57c                      size of os_update.tar.xz

0x02 + 0x026bb5c4 + 0x1a = 0x26bb5e0   start of project.znv
0x002c8934                              size of project.znv
# interpret hexdump:
00000020  48 00 00 00  7c b5 6b 02  ...
00000030  ... "os_update.tar.xz"

00000040  02 00 00 00  c4 b5 6b 02  34 89 2c 00 ...
00000050  ... "project.znv"
 
os_update.tar.xz  offset 0x64       size 0x26bb57c
project.znv       offset 0x26bb5e0  size 0x2c8934

$dd if=Read_regs.ZNX of=os_update.tar.xz bs=1 skip=$((0x64)) count=$((0x26bb57c))

$dd if=Read_regs.ZNX of=project.znv bs=1 skip=$((0x26bb5e0)) count=$((0x2c8934))

$dd if=Read_regs.ZNX of=project.znv bs=1 skip=$((0x26bb5e0)) count=$((0x2c8934))
2918708+0 records in
2918708+0 records out
2918708 bytes (2.9 MB, 2.8 MiB) copied, 2.5951 s, 1.1 MB/s

$ file project.znv 
project.znv: MS Windows cursor resource - 128 icons, 3x256, 18 colors, hotspot @13x35044

$ file os_update.tar.xz 
os_update.tar.xz: XZ compressed data, checksum CRC32

# believe it or not that looks right.
# well, the md5sum is different, but this is a different program than what I started with
$ md5sum os_update.tar.xz 
cc51edc0042ae7d5656c116324edbe98  os_update.tar.xz


$tar -tf os_update.tar.xz
--No Errors

$ mkdir os_files
$ tar -xvf os_update.tar.xz -C os_files/
$ sudo chown -R $USER:$USER os_files/

...hmm I still dont have full permissions. looks like a bunch of link files though.
I wonder if github cares about that. I cewrtainly hope not because Im tired AF, 
and want to look at this later...






</pre>
