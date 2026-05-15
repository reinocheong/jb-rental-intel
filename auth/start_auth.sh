#!/bin/bash
# Start JB Rentals Auth services with Cloudflare Tunnel

LOG="/home/user/jb-rental-intel/.logs/auth.log"
mkdir -p "$(dirname "$LOG")"

echo "[$(date)] Starting auth services..." >> "$LOG"

# Kill old processes
pkill -f "auth_server.py" 2>/dev/null
pkill -f "cloudflared" 2>/dev/null
sleep 1

# Start auth server
cd /home/user/jb-rental-intel
nohup python3 auth/auth_server.py >> "$LOG" 2>&1 &
echo "[$(date)] auth_server PID: $!" >> "$LOG"
sleep 2

# Start cloudflared tunnel
nohup ~/.local/bin/cloudflared tunnel --url http://localhost:8777 > /tmp/cf_url.txt 2>&1 &
echo "[$(date)] cloudflared PID: $!" >> "$LOG"
sleep 6

# Extract URL
CF_URL=$(grep -o 'https://[a-z0-9.-]*\.trycloudflare\.com' /tmp/cf_url.txt | head -1)
if [ -n "$CF_URL" ]; then
    echo "[$(date)] ✅ Tunnel: $CF_URL" >> "$LOG"
    echo "$CF_URL" > /tmp/cf_active_url.txt
else
    echo "[$(date)] ❌ Failed to get tunnel URL" >> "$LOG"
fi

# Verify
if curl -s http://127.0.0.1:8777/health | grep -q '"ok"'; then
    echo "[$(date)] ✅ Auth server healthy" >> "$LOG"
else
    echo "[$(date)] ❌ Auth server not responding" >> "$LOG"
fi
