#!/bin/sh
### BEGIN INIT INFO
# Provides: splash
# Required-Start:
# Required-Stop:
# Default-Start:     S
# Default-Stop:
### END INIT INFO
if [ -e /home/idec/rom/logo.ini ] && [ -e /home/idec/rom/logo.ppm ] ; then
	logofilesize=`wc -c /home/idec/rom/logo.ppm | cut -d' ' -f1`
	if [ $logofilesize -lt 1160000 ] ; then
		fbsplash -s /home/idec/rom/logo.ppm -i /home/idec/rom/logo.ini
	fi
fi

