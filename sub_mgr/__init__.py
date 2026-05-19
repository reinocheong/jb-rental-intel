import sys
from .logic import add_subscriber, start_trial, remind_trials, check_expired, renew_subscriber, process_form, sync_subscriber_sheet
from .db import init_db

def list_subscribers():
    from .db import get_conn
    conn = get_conn()
    rows = conn.execute("SELECT name, email, phone, plan, end_date, status FROM subscribers ORDER BY end_date DESC").fetchall()
    conn.close()
    print(f"{'姓名':<12} {'邮箱':<30} {'电话':<14} {'方案':<6} {'到期':<20} {'状态'}")
    for r in rows: print(f"{r[0]:<12} {r[1]:<30} {r[2]:<14} {r[3]:<6} {r[4]:<20} {r[5]}")

def main():
    init_db()
    if len(sys.argv) < 2: list_subscribers(); return
    cmd = sys.argv[1]
    if cmd == "trial": start_trial(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv)>4 else "basic", sys.argv[5] if len(sys.argv)>5 else "")
    elif cmd == "add": add_subscriber(sys.argv[2], sys.argv[3])
    elif cmd == "remind": remind_trials()
    elif cmd == "check": check_expired()
    elif cmd == "renew": renew_subscriber(sys.argv[2])
    elif cmd == "form-process": process_form()
    elif cmd == "sync": sync_subscriber_sheet()
    elif cmd == "list": list_subscribers()
    else: print("Unknown command")
