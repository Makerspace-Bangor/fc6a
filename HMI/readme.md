#HMI Contents
<pre>
    NOTE: HMI nearly all figured out. Modes, project loading up & down.
          fail statuses, internal register R/W, special commands...
          Its just all scattered in a bunch of individual testing scripts.
          TODO: Wirite MiSMFactory
    
    NOTE: HMI Transport listed as DM Link, internal refferences as DiSm
    Still accuring documentation resources. 
    

HMI/
├── dev
│   ├── hg2j_alarms.py       # Alarms, faults and stats are system specific :(
│   ├── hmi_find.py          # utility to find HMIs, and auto config network for coms
│   ├── hmi_znx_download.py  # Download ZNX files ( OS + Project data)
│   └── readme.md
├── doc2Files                
│   └── readme.md
├── FTP
│   ├── hmi_ftp_shell.py     # open HMI FTP shell, or use filezilla
│   ├── pictures
│   └── readme.md
├── readme.md
├── TOOLS
│   ├── hmi_clear.py        # Factory Reset your HMI
│   ├── hmi_dl_test.py      # change HMI screen
│   ├── hmi_get_ip.py       # Get the IP of the HMI, and the IP it wants coms with
│   ├── hmi_info.py         # Get OEM Data about the HMI in xml format
│   ├── hmi_mode_test.py    # Check / Change HMI Mode
│   ├── hmi_register_logger2.py  # detect, and log HMI. if we integrate hmi_dl_test this will be very useful
│   ├── hmi_registers.txt   # Example hmi_register_logger2.py output
│   ├── readme.md
│   
├── UDP
│   └── udp_select.py       # Unit select using UDP 
└── ZNX
    ├── deconstruct_znv.py  # seperate project files into parts
    ├── extract_znx.py      # seperate ZNX container into OS & project files
    ├── notes
    ├── readme.md
    ├── Read_regs.ZNX       # Test Code
    ├── RIG9.ZNX            # broken code for testing
    └── znx_info.py         # get infor about the ZNX file



</pre>
