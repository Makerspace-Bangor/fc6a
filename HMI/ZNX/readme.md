<pre>
Theres a lot of parts to discect... but you might extract a project.znv from a Named.ZNX,  
so maybe deconstruct_znv.py  
Does belong here. ... and I screwed up, here, but learned some interesting things anyhow:
sn@ker:~/fc6a/HMI/ZNX/test$ ./deconstruct_znv.py RIG9.ZNX 
source: RIG9.ZNX
size:   43816200 bytes / 0x29c9508
magic:  not confirmed
mode:   candidate-scan
found:  70 record(s)

[000] 0x026d16f4       1532  PROJECT.t2f
[001] 0x026d1d14      57984  PROJECT.b2f
[002] 0x026dffb8       2956  mg0001.m2f
[003] 0x026e0b68       6396  PROJECT.i2f
[004] 0x026e2488      37608  PROJECT.d2f
[005] 0x026eb794         28  PROJECT.e2f
[006] 0x026eb7d4        512  PROJECT.s2f
[007] 0x026eb9f8       3788  PROJECT.p2f
[008] 0x026ec8e8       1324  PROJECT.l2f
[009] 0x026ece38      29516  bs0002.o2f
[010] 0x026f41a8      13084  bs0003.o2f
[011] 0x026f74e8       4432  bs0004.o2f
[012] 0x026f865c       4728  bs0005.o2f
[013] 0x026f98f8       1864  bs0006.o2f
[014] 0x026fa064      12252  bs0007.o2f
[015] 0x026fd064      12284  bs0008.o2f
[016] 0x02700084      11216  bs0009.o2f
[017] 0x02702c78      10280  bs0010.o2f
[018] 0x027054c4       7444  bs0011.o2f
[019] 0x027071fc      11132  bs0012.o2f
[020] 0x02709d9c      12688  bs0013.o2f
[021] 0x0270cf50      16072  bs0014.o2f
[022] 0x02710e3c       6468  bs0015.o2f
[023] 0x027127a4      13448  bs0016.o2f
[024] 0x02715c50       7856  bs0017.o2f
[025] 0x02717b24       6404  bs0018.o2f
[026] 0x0271944c       5932  bs0019.o2f
[027] 0x0271ab9c       6344  bs0020.o2f
[028] 0x0271c488       8532  bs0021.o2f
[029] 0x0271e600      17460  bs0022.o2f
[030] 0x02722a58       5208  bs0023.o2f
[031] 0x02723ed4       6516  bs0024.o2f
[032] 0x0272586c       6924  bs0025.o2f
[033] 0x0272739c       9324  bs0026.o2f
[034] 0x0272982c       9364  bs0027.o2f
[035] 0x0272bce4       1868  bs0028.o2f
[036] 0x0272c454       9240  bs0029.o2f
[037] 0x0272e890       8648  bs0030.o2f
[038] 0x02730a7c      15196  bs0031.o2f
[039] 0x027345fc       6520  bs0032.o2f
[040] 0x02735f98      11108  bs0033.o2f
[041] 0x02738b20        728  bs0034.o2f
[042] 0x02738e1c       7952  bs0035.o2f
[043] 0x0273ad50      15320  bs0036.o2f
[044] 0x0273e94c       9188  bs0037.o2f
[045] 0x02740d54      20932  bs0038.o2f
[046] 0x02745f3c       7948  bs0039.o2f
[047] 0x02747e6c       6088  bs0040.o2f
[048] 0x02749658       5364  bs0042.o2f
[049] 0x0274ab70         92  sa0001.o2f
[050] 0x0274abf0       3756  sa3001.o2f
[051] 0x0274bac0       4652  sa3002.o2f
[052] 0x0274cd10       8260  sa3003.o2f
[053] 0x0274ea0c       7388  u.c. (Alphabetical Keypad) 
[054] 0x0274ed78       8260  sa3004.o2f
[055] 0x02750a74       7388  l.c. (Alphabetical Keypad)
[056] 0x02750de0      11612  sa3005.o2f
[057] 0x02753b60       8908  sa3009.o2f
[058] 0x02755e50       8912  sa3010.o2f
[059] 0x02758144      13240  sa3012.o2f
[060] 0x0275afbc      11864  u.c. (Keyboard)
[061] 0x0275b520      13240  sa3013.o2f
[062] 0x0275e398      11864  l.c. (Keyboard)
[063] 0x0275e8fc         40  PROJECT.u2f
[064] 0x0275e948       4156  PROJECT.q2f
[065] 0x0275f9a8      53248  DRIVER1.G2F
[066] 0x0276c9cc       6144  DRIVER2.G2F
[067] 0x0276e1f0       6144  DRIVER3.G2F
[068] 0x0276fa14       6144  DRIVER4.G2F
[069] 0x02771238    2458320  HG2F.BIN

log:      RIG9_znv/extraction.log
manifest: RIG9_znv/manifest.json
scan:     RIG9_znv/filename_scan.txt


## Should have been: 
sn@ker:~/fc6a/HMI/ZNX/test$ ./deconstruct_znv.py RIG9_project.znv 
source: RIG9_project.znv
size:   3112584 bytes / 0x2f7e88
magic:  ZNV at 0x10
mode:   observed-layout
found:  66 record(s)

[000] 0x00000074       1532  PROJECT.t2f
[001] 0x00000694      57984  PROJECT.b2f
[002] 0x0000e938       2956  mg0001.m2f
[003] 0x0000f4e8       6396  PROJECT.i2f
[004] 0x00010e08      37608  PROJECT.d2f
[005] 0x0001a114         28  PROJECT.e2f
[006] 0x0001a154        512  PROJECT.s2f
[007] 0x0001a378       3788  PROJECT.p2f
[008] 0x0001b268       1324  PROJECT.l2f
[009] 0x0001b7b8      29516  bs0002.o2f
[010] 0x00022b28      13084  bs0003.o2f
[011] 0x00025e68       4432  bs0004.o2f
[012] 0x00026fdc       4728  bs0005.o2f
[013] 0x00028278       1864  bs0006.o2f
[014] 0x000289e4      12252  bs0007.o2f
[015] 0x0002b9e4      12284  bs0008.o2f
[016] 0x0002ea04      11216  bs0009.o2f
[017] 0x000315f8      10280  bs0010.o2f
[018] 0x00033e44       7444  bs0011.o2f
[019] 0x00035b7c      11132  bs0012.o2f
[020] 0x0003871c      12688  bs0013.o2f
[021] 0x0003b8d0      16072  bs0014.o2f
[022] 0x0003f7bc       6468  bs0015.o2f
[023] 0x00041124      13448  bs0016.o2f
[024] 0x000445d0       7856  bs0017.o2f
[025] 0x000464a4       6404  bs0018.o2f
[026] 0x00047dcc       5932  bs0019.o2f
[027] 0x0004951c       6344  bs0020.o2f
[028] 0x0004ae08       8532  bs0021.o2f
[029] 0x0004cf80      17460  bs0022.o2f
[030] 0x000513d8       5208  bs0023.o2f
[031] 0x00052854       6516  bs0024.o2f
[032] 0x000541ec       6924  bs0025.o2f
[033] 0x00055d1c       9324  bs0026.o2f
[034] 0x000581ac       9364  bs0027.o2f
[035] 0x0005a664       1868  bs0028.o2f
[036] 0x0005add4       9240  bs0029.o2f
[037] 0x0005d210       8648  bs0030.o2f
[038] 0x0005f3fc      15196  bs0031.o2f
[039] 0x00062f7c       6520  bs0032.o2f
[040] 0x00064918      11108  bs0033.o2f
[041] 0x000674a0        728  bs0034.o2f
[042] 0x0006779c       7952  bs0035.o2f
[043] 0x000696d0      15320  bs0036.o2f
[044] 0x0006d2cc       9188  bs0037.o2f
[045] 0x0006f6d4      20932  bs0038.o2f
[046] 0x000748bc       7948  bs0039.o2f
[047] 0x000767ec       6088  bs0040.o2f
[048] 0x00077fd8       5364  bs0042.o2f
[049] 0x000794f0         92  sa0001.o2f
[050] 0x00079570       3756  sa3001.o2f
[051] 0x0007a440       4652  sa3002.o2f
[052] 0x0007b690       8260  sa3003.o2f
[053] 0x0007d6f8       8260  sa3004.o2f
[054] 0x0007f760      11612  sa3005.o2f
[055] 0x000824e0       8908  sa3009.o2f
[056] 0x000847d0       8912  sa3010.o2f
[057] 0x00086ac4      13240  sa3012.o2f
[058] 0x00089ea0      13240  sa3013.o2f
[059] 0x0008d27c         40  PROJECT.u2f
[060] 0x0008d2c8       4156  PROJECT.q2f
[061] 0x0008e328      53248  DRIVER1.G2F
[062] 0x0009b34c       6144  DRIVER2.G2F
[063] 0x0009cb70       6144  DRIVER3.G2F
[064] 0x0009e394       6144  DRIVER4.G2F
[065] 0x0009fbb8    2458320  HG2F.BIN

log:      RIG9_project_znv/extraction.log
manifest: RIG9_project_znv/manifest.json
scan:     RIG9_project_znv/filename_scan.txt



project offset = os_update offset + os_update size
0x64 + 0x26bb57c = 0x26bb5e0


<b>$ znx_info.py screens2.ZNX</b> 

screens2.ZNX
============
size: 0x2929c64 (43162724 bytes)
header total-0x1c: 0x2929c48 (OK)
members: 2
      offset          size        stored      mystery   crc32     sha256                                                            name
------------  ------------  ------------  ------------  --------  -----------------------------------------------------------       ----------------
0x00000064      0x026bb57c   0x00000048     0xc02c91a6  1376a72a  5905b827b3c80046809f699a258b12d6721ecfb0dbc06f05bb4f25a62bd7610e  os_update.tar.xz
0x026bb5e0      0x0026e684   0x026bb5c4     0x55235880  790c7d17  aac3e00c6d6e19ef06bf178bade334a1cf3425f40eb25779d7e7e5f97855fc7d  project.znv
linux:
  os-release: Arago 2019.07
  version_id: 2019.07
  /etc/version: 20241129010957
  /etc/timestamp: 20241129011703
nested archives:
  os_update.tar.xz -> ./home/root/boot-update.tar.xz
  os_update.tar.xz -> ./home/root/boot-update.tar.xz -> ntfs-3g_2017.3.23-r0_armv7at2hf-neon.tar.xz
  os_update.tar.xz -> ./home/root/boot-update.tar.xz -> ntfsprogs_2017.3.23-r0_armv7at2hf-neon.tar.xz
  

</pre>
# Sample Extraction 
<pre>
<b>$ ./extract_znx.py Read_regs.ZNX</b> 
found 2 file(s)

      offset          size        stored  name
------------  ------------  ------------  --------------------------------
0x00000064    0x026bb57c    0x00000048    os_update.tar.xz
0x026bb5e0    0x002c8934    0x026bb5c4    project.znv

extracted 2 file(s) to Read_regs

</pre>
