<pre>
HMI_DEV:
├── hg2j_alarms.py       # faults and errs if any
├── hmi_find.py          # config **1
├── hmi_znx_download.py  # znx os + program download
└── readme.md

**1" scans network, finds, and configures your network 
interface to the hmi. then simulates being the plc the 
hmi is requesting. works on linux great, but windows
netsh command hasnt worked right. 

HG2F.BIN == idec_operation.BIN
HG2F.BIN = is the arm binary in the znv files
idec_operation.BIN = the project runtime
Today I realized they are the same file

sn@ker:~/fc6a/HMI/dev/test/Read_regs/os_update/home/root$ sha256sum \
  ~/fc6a/HMI/dev/test/Read_regs/os_update/home/root/idec_operation.BIN \
  ~/fc6a/HMI/dev/test/Read_regs_znv/files/HG2F.BIN
53fefb4d107b7c4ac8895a8cd50f892cd96aafef08d31206d1e80c3cc1da0b57  /home/sn/fc6a/HMI/dev/test/Read_regs/os_update/home/root/idec_operation.BIN
53fefb4d107b7c4ac8895a8cd50f892cd96aafef08d31206d1e80c3cc1da0b57  /home/sn/fc6a/HMI/dev/test/Read_regs_znv/files/HG2F.BIN

kinda makes me wonder what other project files are 
embeded in the os files.
file exploration:  
~/AO/WindOI-NV4/ConfigurationData/Common/RuntimeSys/HG2J_SYSTEM.BIN  
~/AO/WindOI-NV4/ConfigurationData/Common/RuntimeSys/HG2J_OS.BIN  

</pre>
