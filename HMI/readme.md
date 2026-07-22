#HMI Contents
<pre>


HMI/
├── FTP
│   ├── hmi_ftp_shell.py   Utility to use the system FTP session. its how ZNX uploads work. 
│   
├── TOOLS
│   ├── hmi_clear.py       Errase the HMI
│   ├── hmi_get_ip.py      Get the IP of the HMI, and the IP it wants coms with
│   ├── hmi_info.py        Get OEM Data about the HMI in xml format
│   ├── hmi_register_logger2.py  Initialize the HMI, and listen for its requests
│   ├── hmi_registers.txt        Example hmi_register_logger2.py output
│   
└── ZNX
    ├── tools
    │   ├── extract_znx.py   Utility to extract files from ZNX
    │   ├── Read_regs.ZNX    Example HMI program with firmware
    │   └── znx_info.py      Info about the ZNX container
    └── untar.txt





</pre>
