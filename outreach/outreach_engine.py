#!/usr/bin/env python3
import sys, os, json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0, "/home/user/jb-rental-intel")

from outreach.lib.wa_sender import send_whatsapp, check_daemon_alive
from outreach.lib.sheets_tracker import get_agents_from_sheet, get_outreach_records, append_outreach_record, get_subscribed_phones
from outreach.lib.quota_utils import calculate_dynamic_quota, pick_slot_candidates

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")

def log(msg):
    print(f"[{datetime.now(MY_TZ).strftime('%Y-%m-%d %H:%M:%S')}] [outreach_engine.py] {msg}")

def run(dry_run=True, slot=0, total_slots=1):
    log("🚀 Outreach Engine 开始")
    if not dry_run and not check_daemon_alive(): return {"error": "daemon_down"}
    
    agents = get_agents_from_sheet()
    records = get_outreach_records()
    subscribed = get_subscribed_phones()
    
    daily_quota = calculate_dynamic_quota(len(agents), len(records))
    candidates = [a for a in agents if a.get('phone') not in subscribed] # Simplified for brevity
    slot_candidates = pick_slot_candidates(candidates, slot, total_slots)[:max(1, daily_quota // total_slots)]
    
    sent = 0
    for i, c in enumerate(slot_candidates):
        template = "A" if i % 2 == 0 else "B"
        if dry_run: log(f"🧪 干跑: {c['phone']} ({template})"); sent += 1
        elif send_whatsapp(c["phone"], template)["ok"]:
            append_outreach_record({"phone": c["phone"], "agent": c["agent"], "template": template, "status": "已发送"})
            sent += 1
    log(f"✅ 完成: 发送 {sent}")
    return {"sent": sent}

if __name__ == "__main__":
    dry_run = "--send" not in sys.argv
    slot = int(next((sys.argv[i+1] for i, v in enumerate(sys.argv) if v == "--slot"), 1)) - 1
    total = int(next((sys.argv[i+1] for i, v in enumerate(sys.argv) if v == "--total-slots"), 1))
    run(dry_run, slot, total)
