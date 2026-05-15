#!/bin/bash
# @reboot cron entry for wa_daemon
sleep 5
cd /home/user/jb-rental-intel
ln -sf ../wa_session wa/wa_session
nohup node wa/wa_daemon.js >> .logs/wa_daemon.log 2>&1 &
echo "[$(date)] wa_daemon started (PID: $!)" >> .logs/wa_daemon.log
