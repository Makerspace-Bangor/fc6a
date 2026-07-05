<pre>
The ZNX file is a program binary, file archive of both the linux version
and, your program code. The HMI can read the ZNX files by either, having them in the 
HGATA01/NVDATA folder, with an ini file pointing the OS to extract the file,
or via standard program download.

Notes.txt     for process notes
Toos/         for some tools related to znx files
untar.txt     A list of the package contents for the os_upade.tar.xz 
              Embeded file.

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
