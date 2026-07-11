<pre>
The ZNX file is a program binary, file archive of both the linux version
and, your program code. The HMI can read the ZNX files by either, having them in the 
HGATA01/NVDATA folder, with an ini file pointing the OS to extract the file,
or via standard program download.

Notes.txt     for process notes
Toos/         for some tools related to znx files and programing the HMI
untar.txt     A list of the package contents for the os_upade.tar.xz 
              Embeded file.

##################################
# How the download seems to work #
##################################

you create a ZNX, then dowload it with DataFileManager.
What is happening behind the scenes
And FTP session is created, on port 2539
a random user and password is generated
Your ZNX file is renamed "os_update.znx"
this is uploaded to tmp/ on the HMI FTP server.
an MD5 checksum of your ZNX file is created, and uploaded
to the same tmp/ location. 

The HMI then runs some command to update the linux.
The HMI reboots. 
then your progam code is extracted, and installed.
A backup of the exracted code is saved as project.znv
in the tmp/ folder. 

All the steps are orchistrated via Maintenance Protocol type 
Commands. All the tools are based on these sequences. 
Is there documentation for this? LOL I have seen it!
but I didnt save it! I should have!

But, I know they called it DiSm.

Read_regs.ZNX an example ZNX file
extracted/:   the "FIRMWARE" extracted 

$tree -L 2 ZNX
ZNX
├── extracted
│   ├── os_files
│   ├── os_update.tar.xz
│   └── project.znv
├── notes.txt
├── readme.md
├── Read_regs.ZNX
├── tools
│   ├── extract_znx.py
│   └── znx_info.py
└── untar.txt


</pre>
