Here I figure out all the neat things you can do with an IDEC HG2J-7U HMI.
<pre>

<b>TL;DR:</b> It is LINUX!

ID="arago"
NAME="Arago"
VERSION="2019.07"
VERSION_ID="2019.07"
PRETTY_NAME="Arago 2019.07"
os-release (END)

Arago Linux (or the Arago Project) is an open-source Linux distribution 
created and maintained by Texas Instruments. 


There is FTP

Plug in a mouse: you get a cursor

Plug in a keyboard: ... you dont get keys like you might expect.
but, the magic keys: alt + sysreq + <key> do have some effect.
The first thing I tried was REISUB. This did not operated as expected.

alt + sysreq + R = "boot screen"
alt + sysreq + B = reload program screen, led goes orange
alt + sysreq + K = blank scree, LED green the whole time. pressing again, no effect
alt + sysreq + V = same as K
alt + sysreq +  =
alt + sysreq +  =
alt + sysreq +  =
alt + sysreq +  =


Whether or not what is called the boot screen is a true boot screen is 
unknown. it doesnt behave like a true boot screen, but the keys are 
not mapped in a normal, sane mapping... so Im figuring that out. 


LF0F    -> ACK
FTP uploads os_update.znx
FTP uploads os_update.znx.md5
LC 01 00 -> final command

durring download:
NV4 sends:
00FFAB06
00FFAD00
00FFLA08
00FFLE0C
00FFLB...
00FFLF0F
 FTP appears on 2539, and the actual .ZNX is pushed over FTP/data port 2541
## from capture 
$ nmap -Pn -p100-65535 192.168.1.20
Starting Nmap 7.94SVN ( https://nmap.org ) at 2026-07-02 20:38 EDT
Nmap scan report for 192.168.1.20
Host is up (0.0037s latency).
Not shown: 65433 closed tcp ports (conn-refused)
PORT     STATE SERVICE
2537/tcp open  upgrade
2539/tcp open  vsiadmin
2541/tcp open  lonworks2

2537: enter download mode
2539: FTP PUT os_update.znx
2539: FTP PUT os_update.znx.md5
2537: LC
2537: LD
2537: AH

no idea where though. its not in the err... user ftp
AB / AD / LA / LE / LB / LF  -> enter/start FTP download mode
LC / LD / AH                 -> commit / reload (reboot) /exit


 
</pre>
