<pre>
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
