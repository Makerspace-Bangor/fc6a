# took an image of the HMI and made a back up.
<pre>
then I got the bright idea to run it in docker.
thats what run.sh is for. there a lot of files 
and none of it really works right now. 

I find the broken files, suplement them, and retry. 

its not running right, right now.
its now crashing futher down its initialization process.

how feasible it is... IDK. 
Maybe?

the screen /dev/dri/card0 will have to be emulated. 
root@am335x-idec-pd:/home/service# mount /dev/dri/renderD128  card/
mount: /home/service/card: /dev/dri/renderD128 is not a block device.
root@am335x-idec-pd:/home/service# ls -al /dev/dri/*
crwxrwxrwx    1 root     video     226,   0 Oct 24 00:59 /dev/dri/card0
crw-rw----    1 root     video     226,   1 Oct 24 00:59 /dev/dri/card1
crw-rw-rw-    1 root     video     226, 128 Oct 24 00:59 /dev/dri/renderD128

/dev/dri/by-path:
drwxr-xr-x    2 root     root           100 Oct 24 00:59 .
drwxr-xr-x    3 root     root           120 Oct 24 00:59 ..
lrwxrwxrwx    1 root     root             8 Oct 24 00:59 platform-4830e000.lcdc-card -> ../card0
lrwxrwxrwx    1 root     root             8 Oct 24 00:59 platform-56000000.sgx-card -> ../card1
lrwxrwxrwx    1 root     root            13 Oct 24 00:59 platform-56000000.sgx-render -> ../renderD128


But I dont even care, because its still not stable.

</pre>

