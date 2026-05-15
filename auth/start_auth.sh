#!/bin/bash
# JB Rentals Auth — 启动 auth_server + bore tunnel
# 放到 crontab: @reboot bash /home/user/jb-rental-intel/auth/start_auth.sh

LOG="/home/user/jb-rental-intel/.logs/auth.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] Starting auth services..." >> "$LOG"

# Kill old processes if any
pkill -f "auth_server.py" 2>/dev/null
pkill -f "bore local 8777" 2>/dev/null
sleep 1

# Start auth server
cd /home/user/jb-rental-intel
nohup python3 auth/auth_server.py >> "$LOG" 2>&1 &
echo "[$(date)] auth_server PID: $!" >> "$LOG"

# Wait for server to be ready
sleep 2

# Start bore tunnel
nohup ~/.local/bin/bore local 8777 --to bore.pub --port 44200 >> "$LOG" 2>&1 &
echo "[$(date)] bore tunnel PID: $!" >> "$LOG"

sleep 3

# Verify
if curl -s http://127.0.0.1:8777/health | grep -q '"ok"'; then
    echo "[$(date)] ✅ Auth server healthy" >> "$LOG"
else
    echo "[$(date)] ❌ Auth server not responding" >> "$LOG"
fi

echo "[$(date)] Services started" >> "$LOG"
