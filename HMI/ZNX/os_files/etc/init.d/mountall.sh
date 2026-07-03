#!/bin/sh
### BEGIN INIT INFO
# Provides:          mountall
# Required-Start:    mountvirtfs
# Required-Stop: 
# Default-Start:     S
# Default-Stop:
# Short-Description: Mount all filesystems.
# Description:
### END INIT INFO

. /etc/default/rcS

# create the path that idec needs & remount the fs
if [ ! -d /home/idec/.tmp ];then
  /bin/mkdir -m 777 /home/idec/.tmp
fi

if [ ! -d /home/idec/.work ];then
  /bin/mkdir -m 777 /home/idec/.work
fi

if [ ! -d /home/idec/rom ];then
  /bin/mkdir -m 777 /home/idec/rom
fi

if [ ! -d /home/idec/usr ];then
  /bin/mkdir -m 777 /home/idec/usr/
fi

if [ ! -d /home/idec/usr/tmp ];then
  /bin/mkdir -m 777 /home/idec/usr/tmp
fi

# forbidden normal users write anyting on rom through FTP Server
if [ ! -d /home/idec/usr/exmem ];then
  /bin/mkdir -m 555 /home/idec/usr/exmem
fi

if [ ! -d /mnt/work ];then
  /bin/mkdir -m 777 /mnt/work
fi

#
# Mount local filesystems in /etc/fstab. For some reason, people
# might want to mount "proc" several times, and mount -v complains
# about this. So we mount "proc" filesystems without -v.
#
test "$VERBOSE" != no && echo "Mounting local filesystems..."
mount -at nonfs,nosmbfs,noncpfs 2>/dev/null

#
# We might have mounted something over /dev, see if /dev/initctl is there.
#
if test ! -p /dev/initctl
then
	rm -f /dev/initctl
	mknod -m 600 /dev/initctl p
fi
kill -USR1 1

: exit 0

