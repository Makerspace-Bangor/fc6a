
HMI_DEV:
├── hg2j_alarms.py       # faults and errs if any
├── hmi_find.py          # config **1
├── hmi_znx_download.py  # znx os + program download
└── readme.md

**1" scans network, finds, and configures your network 
interface to the hmi. then simulates being the plc the 
hmi is requesting. works on linux great, but windows
netsh command hasnt worked right. 
