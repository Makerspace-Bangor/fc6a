#!/bin/sh
cp /home/root/idec_operation.BIN /home/idec/.tmp &
insmod /lib/modules/$(uname -r)/extra/pvrsrvkm.ko
grep -q tp=1 /proc/cmdline && insmod /lib/modules/$(uname -r)/kernel/drivers/input/touchscreen/hycon/hy461x_ts.ko
