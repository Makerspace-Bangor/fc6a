## SnaKer Test Files
<pre>
sn@ker:~$ 
find ~/fc6a -type d -name test -exec sh -c '
    for dir do
        echo
        echo "===== $dir ====="
        tree -L 3 "$dir"
    done
' sh {} +

===== /home/sn/fc6a/PLC/ZLD/test =====
/home/sn/fc6a/PLC/ZLD/test
├── download_zld.py
└── MiSmSerial.py

1 directory, 2 files

===== /home/sn/fc6a/HMI/dev/test =====
/home/sn/fc6a/HMI/dev/test
├── bs.ZNX
├── deconstruct_znv.py
├── extract_znx.py
├── hg2j_alarms.py
├── hmi_dl_test.py
├── hmi_mode_test.py
├── hmi_znx_download.py
├── OLD
│   ├── Read_regs
│   │   ├── os_update
│   │   ├── os_update.tar.xz
│   │   └── project.znv
│   ├── Read_regs_znv
│   │   ├── extraction.log
│   │   ├── filename_scan.txt
│   │   ├── files
│   │   ├── manifest.json
│   │   └── znv_header.bin
│   ├── Read_regs.ZNX
│   └── rpk.ZNX
├── os_mods.ZNX
├── __pycache__
│   └── hg2j_alarms.cpython-312.pyc
├── Read_regsMod.ZNX
├── Read_regs.ZNX
├── repack_znx_fixed.py
├── repack_znx.py
├── rgb_47
│   ├── os_update
│   │   ├── bin
│   │   ├── boot
│   │   ├── dev
│   │   ├── etc
│   │   ├── home
│   │   ├── lib
│   │   ├── linuxrc -> /bin/busybox.nosuid
│   │   ├── media
│   │   ├── mnt
│   │   ├── proc
│   │   ├── run
│   │   ├── sbin
│   │   ├── sys
│   │   ├── tmp -> var/tmp
│   │   ├── usr
│   │   └── var
│   ├── os_update.tar.xz
│   └── project.znv
├── rgb_47_znv
│   ├── extraction.log
│   ├── filename_scan.txt
│   ├── files
│   │   ├── bs0001.o2f
│   │   ├── bs0002.o2f
│   │   ├── bs0003.o2f
│   │   ├── DRIVER1.G2F
│   │   ├── DRIVER2.G2F
│   │   ├── DRIVER3.G2F
│   │   ├── DRIVER4.G2F
│   │   ├── HG2F.BIN
│   │   ├── l.c.__Alphabetical_Keypad_
│   │   ├── l.c.__Keyboard_
│   │   ├── mg0001.m2f
│   │   ├── PROJECT.b2f
│   │   ├── PROJECT.d2f
│   │   ├── PROJECT.e2f
│   │   ├── PROJECT.i2f
│   │   ├── PROJECT.l2f
│   │   ├── PROJECT.p2f
│   │   ├── PROJECT.q2f
│   │   ├── PROJECT.s2f
│   │   ├── PROJECT.t2f
│   │   ├── PROJECT.u2f
│   │   ├── sa3001.o2f
│   │   ├── sa3002.o2f
│   │   ├── sa3003.o2f
│   │   ├── sa3004.o2f
│   │   ├── sa3005.o2f
│   │   ├── sa3009.o2f
│   │   ├── sa3010.o2f
│   │   ├── sa3011.o2f
│   │   ├── sa3012.o2f
│   │   ├── sa3013.o2f
│   │   ├── u.c.__Alphabetical_Keypad__
│   │   └── u.c.__Keyboard_
│   ├── manifest.json
│   └── znv_header.bin
├── rgb_47.ZNX
├── rgb_51
│   ├── os_update
│   │   ├── bin
│   │   ├── boot
│   │   ├── dev
│   │   ├── etc
│   │   ├── home
│   │   ├── lib
│   │   ├── linuxrc -> /bin/busybox.nosuid
│   │   ├── media
│   │   ├── mnt
│   │   ├── proc
│   │   ├── run
│   │   ├── sbin
│   │   ├── sys
│   │   ├── tmp -> var/tmp
│   │   ├── usr
│   │   └── var
│   ├── os_update.tar.gz
│   ├── os_update.tar.xz
│   └── project.znv
├── rgb_51_znv
│   ├── extraction.log
│   ├── filename_scan.txt
│   ├── files
│   │   ├── bs0001.o2f
│   │   ├── bs0002.o2f
│   │   ├── bs0003.o2f
│   │   ├── DRIVER1.G2F
│   │   ├── DRIVER2.G2F
│   │   ├── DRIVER3.G2F
│   │   ├── DRIVER4.G2F
│   │   ├── HG2F.BIN
│   │   ├── l.c.__Alphabetical_Keypad_
│   │   ├── l.c.__Keyboard_
│   │   ├── mg0001.m2f
│   │   ├── PROJECT.b2f
│   │   ├── PROJECT.d2f
│   │   ├── PROJECT.e2f
│   │   ├── PROJECT.i2f
│   │   ├── PROJECT.l2f
│   │   ├── PROJECT.p2f
│   │   ├── PROJECT.q2f
│   │   ├── PROJECT.s2f
│   │   ├── PROJECT.t2f
│   │   ├── PROJECT.u2f
│   │   ├── sa3001.o2f
│   │   ├── sa3002.o2f
│   │   ├── sa3003.o2f
│   │   ├── sa3004.o2f
│   │   ├── sa3005.o2f
│   │   ├── sa3009.o2f
│   │   ├── sa3010.o2f
│   │   ├── sa3011.o2f
│   │   ├── sa3012.o2f
│   │   ├── sa3013.o2f
│   │   ├── u.c.__Alphabetical_Keypad__
│   │   └── u.c.__Keyboard_
│   ├── manifest.json
│   └── znv_header.bin
├── rgb_51.ZNX
├── znx_hg2f_check.py
└── znx_hg2f.py

43 directories, 108 files

===== /home/sn/fc6a/HMI/ZNX/test =====
/home/sn/fc6a/HMI/ZNX/test
├── deconstruct_znv.py
├── extract_znx.py
├── hgauto.ini
├── project.znv
├── project_znv
│   ├── extraction.log
│   ├── filename_scan.txt
│   ├── files
│   │   ├── BS0001.o2f
│   │   ├── BS0002.o2f
│   │   ├── BS0003.o2f
│   │   ├── BS0004.o2f
│   │   ├── BS0005.o2f
│   │   ├── BS0006.o2f
│   │   ├── BS0007.o2f
│   │   ├── BS0008.o2f
│   │   ├── BS0009.o2f
│   │   ├── BS0010.o2f
│   │   ├── BS0011.o2f
│   │   ├── BS0012.o2f
│   │   ├── BS0013.o2f
│   │   ├── BS0014.o2f
│   │   ├── BS0015.o2f
│   │   ├── BS0016.o2f
│   │   ├── BS0017.o2f
│   │   ├── BS0018.o2f
│   │   ├── BS0019.o2f
│   │   ├── BS0020.o2f
│   │   ├── BS0021.o2f
│   │   ├── BS0022.o2f
│   │   ├── BS0023.o2f
│   │   ├── BS0024.o2f
│   │   ├── BS0025.o2f
│   │   ├── BS0026.o2f
│   │   ├── BS0027.o2f
│   │   ├── BS0028.o2f
│   │   ├── BS0029.o2f
│   │   ├── BS0030.o2f
│   │   ├── BS0031.o2f
│   │   ├── BS0032.o2f
│   │   ├── BS0033.o2f
│   │   ├── BS0034.o2f
│   │   ├── BS0035.o2f
│   │   ├── BS0036.o2f
│   │   ├── BS0037.o2f
│   │   ├── BS0038.o2f
│   │   ├── BS0039.o2f
│   │   ├── BS0040.o2f
│   │   ├── BS0042.o2f
│   │   ├── DRIVER1.G2F
│   │   ├── DRIVER2.G2F
│   │   ├── DRIVER3.G2F
│   │   ├── DRIVER4.G2F
│   │   ├── HG2F.BIN
│   │   ├── MG0001.m2f
│   │   ├── PROJECT.b2f
│   │   ├── PROJECT.d2f
│   │   ├── PROJECT.e2f
│   │   ├── PROJECT.i2f
│   │   ├── PROJECT.l2f
│   │   ├── PROJECT.p2f
│   │   ├── PROJECT.q2f
│   │   ├── PROJECT.s2f
│   │   ├── PROJECT.t2f
│   │   ├── PROJECT.u2f
│   │   ├── SA0001.o2f
│   │   ├── SA3001.o2f
│   │   ├── SA3002.o2f
│   │   ├── SA3003.o2f
│   │   ├── SA3004.o2f
│   │   ├── SA3005.o2f
│   │   ├── SA3009.o2f
│   │   ├── SA3010.o2f
│   │   ├── SA3012.o2f
│   │   └── SA3013.o2f
│   ├── manifest.json
│   └── znv_header.bin
├── Read_regs
│   ├── os_update
│   │   ├── bin
│   │   ├── boot
│   │   ├── dev
│   │   ├── etc
│   │   ├── home
│   │   ├── lib
│   │   ├── linuxrc -> /bin/busybox.nosuid
│   │   ├── media
│   │   ├── mnt
│   │   ├── proc
│   │   ├── run
│   │   ├── sbin
│   │   ├── sys
│   │   ├── tmp -> var/tmp
│   │   ├── usr
│   │   └── var
│   ├── os_update.tar.xz
│   └── project.znv
├── Read_regs.ZNX
├── repack_znx_fixed.py
├── repack_znx.py
├── repak_dev
│   ├── repacktest1.sh
│   ├── repack_znx_fixed.py
│   ├── repack_znx.py
│   └── rpk.ZNX
├── RIG9_project.znv
├── RIG9_project_znv
│   ├── extraction.log
│   ├── filename_scan.txt
│   ├── files
│   │   ├── bs0002.o2f
│   │   ├── bs0003.o2f
│   │   ├── bs0004.o2f
│   │   ├── bs0005.o2f
│   │   ├── bs0006.o2f
│   │   ├── bs0007.o2f
│   │   ├── bs0008.o2f
│   │   ├── bs0009.o2f
│   │   ├── bs0010.o2f
│   │   ├── bs0011.o2f
│   │   ├── bs0012.o2f
│   │   ├── bs0013.o2f
│   │   ├── bs0014.o2f
│   │   ├── bs0015.o2f
│   │   ├── bs0016.o2f
│   │   ├── bs0017.o2f
│   │   ├── bs0018.o2f
│   │   ├── bs0019.o2f
│   │   ├── bs0020.o2f
│   │   ├── bs0021.o2f
│   │   ├── bs0022.o2f
│   │   ├── bs0023.o2f
│   │   ├── bs0024.o2f
│   │   ├── bs0025.o2f
│   │   ├── bs0026.o2f
│   │   ├── bs0027.o2f
│   │   ├── bs0028.o2f
│   │   ├── bs0029.o2f
│   │   ├── bs0030.o2f
│   │   ├── bs0031.o2f
│   │   ├── bs0032.o2f
│   │   ├── bs0033.o2f
│   │   ├── bs0034.o2f
│   │   ├── bs0035.o2f
│   │   ├── bs0036.o2f
│   │   ├── bs0037.o2f
│   │   ├── bs0038.o2f
│   │   ├── bs0039.o2f
│   │   ├── bs0040.o2f
│   │   ├── bs0042.o2f
│   │   ├── DRIVER1.G2F
│   │   ├── DRIVER2.G2F
│   │   ├── DRIVER3.G2F
│   │   ├── DRIVER4.G2F
│   │   ├── HG2F.BIN
│   │   ├── mg0001.m2f
│   │   ├── PROJECT.b2f
│   │   ├── PROJECT.d2f
│   │   ├── PROJECT.e2f
│   │   ├── PROJECT.i2f
│   │   ├── PROJECT.l2f
│   │   ├── PROJECT.p2f
│   │   ├── PROJECT.q2f
│   │   ├── PROJECT.s2f
│   │   ├── PROJECT.t2f
│   │   ├── PROJECT.u2f
│   │   ├── sa0001.o2f
│   │   ├── sa3001.o2f
│   │   ├── sa3002.o2f
│   │   ├── sa3003.o2f
│   │   ├── sa3004.o2f
│   │   ├── sa3005.o2f
│   │   ├── sa3009.o2f
│   │   ├── sa3010.o2f
│   │   ├── sa3012.o2f
│   │   └── sa3013.o2f
│   ├── manifest.json
│   └── znv_header.bin
├── RIG9_znv
│   ├── extraction.log
│   ├── filename_scan.txt
│   ├── files
│   │   ├── bs0002.o2f
│   │   ├── bs0003.o2f
│   │   ├── bs0004.o2f
│   │   ├── bs0005.o2f
│   │   ├── bs0006.o2f
│   │   ├── bs0007.o2f
│   │   ├── bs0008.o2f
│   │   ├── bs0009.o2f
│   │   ├── bs0010.o2f
│   │   ├── bs0011.o2f
│   │   ├── bs0012.o2f
│   │   ├── bs0013.o2f
│   │   ├── bs0014.o2f
│   │   ├── bs0015.o2f
│   │   ├── bs0016.o2f
│   │   ├── bs0017.o2f
│   │   ├── bs0018.o2f
│   │   ├── bs0019.o2f
│   │   ├── bs0020.o2f
│   │   ├── bs0021.o2f
│   │   ├── bs0022.o2f
│   │   ├── bs0023.o2f
│   │   ├── bs0024.o2f
│   │   ├── bs0025.o2f
│   │   ├── bs0026.o2f
│   │   ├── bs0027.o2f
│   │   ├── bs0028.o2f
│   │   ├── bs0029.o2f
│   │   ├── bs0030.o2f
│   │   ├── bs0031.o2f
│   │   ├── bs0032.o2f
│   │   ├── bs0033.o2f
│   │   ├── bs0034.o2f
│   │   ├── bs0035.o2f
│   │   ├── bs0036.o2f
│   │   ├── bs0037.o2f
│   │   ├── bs0038.o2f
│   │   ├── bs0039.o2f
│   │   ├── bs0040.o2f
│   │   ├── bs0042.o2f
│   │   ├── DRIVER1.G2F
│   │   ├── DRIVER2.G2F
│   │   ├── DRIVER3.G2F
│   │   ├── DRIVER4.G2F
│   │   ├── HG2F.BIN
│   │   ├── l.c.__Alphabetical_Keypad_
│   │   ├── l.c.__Keyboard_
│   │   ├── mg0001.m2f
│   │   ├── PROJECT.b2f
│   │   ├── PROJECT.d2f
│   │   ├── PROJECT.e2f
│   │   ├── PROJECT.i2f
│   │   ├── PROJECT.l2f
│   │   ├── PROJECT.p2f
│   │   ├── PROJECT.q2f
│   │   ├── PROJECT.s2f
│   │   ├── PROJECT.t2f
│   │   ├── PROJECT.u2f
│   │   ├── sa0001.o2f
│   │   ├── sa3001.o2f
│   │   ├── sa3002.o2f
│   │   ├── sa3003.o2f
│   │   ├── sa3004.o2f
│   │   ├── sa3005.o2f
│   │   ├── sa3009.o2f
│   │   ├── sa3010.o2f
│   │   ├── sa3012.o2f
│   │   ├── sa3013.o2f
│   │   ├── u.c.__Alphabetical_Keypad__
│   │   └── u.c.__Keyboard_
│   ├── manifest.json
│   └── znv_header.bin
├── rpk.ZNX
├── X_RIG9
│   ├── os_update.tar.xz
│   └── project.znv
├── X_RIG9.ZNX
└── znx_tool.py

25 directories, 236 files
</pre>
