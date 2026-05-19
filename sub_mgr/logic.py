import json, os, subprocess, sqlite3, re
from datetime import datetime, timedelta
from .db import get_conn
from .google_ops import share_sheet, revoke_sheet, check_shared, get_sheets_service, get_forms_service
from .notifications import wa_send, wa_lid

MY_TZ_OFFSET = timedelta(hours=8)
PROCESSED_FILE = "/home/user/jb-rental-intel/.form_processed.json"
FORM_ID = "1oZTQNl3PF8TOu7RsG2SZeGjx5goT-o2Jy0TL7RlBiIQ"
FORM_SHEET_ID = "1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"

def add_subscriber(email, name, plan="basic", phone="", days=30):
    print(f"[sub_mgr/logic.py][db] 添加订阅: {email}")
    conn = get_conn()
    now = datetime.utcnow() + MY_TZ_OFFSET
    start = now.strftime("%Y-%m-%d %H:%M:%S")
    end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        conn.execute("INSERT INTO subscribers (email, name, phone, plan, start_date, end_date, status) VALUES (?,?,?,?,?,?,?)",
            (email.lower().strip(), name.strip(), phone.strip(), plan, start, end, "active"))
        conn.commit()
        perm_id = share_sheet(email)
        if perm_id:
            conn.execute("UPDATE subscribers SET permission_id=? WHERE email=?", (perm_id, email.lower().strip()))
            conn.commit()
        print(f"✅ {name} 订阅已开通")
        return True
    except sqlite3.IntegrityError: return False
    finally: conn.close()

def start_trial(email, name, plan="basic", phone=""):
    print(f"[sub_mgr/logic.py][db] 开启试用: {email}")
    conn = get_conn()
    now = datetime.utcnow() + MY_TZ_OFFSET
    start = now.strftime("%Y-%m-%d %H:%M:%S")
    end = (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    try:
        lid = wa_lid(phone)
        conn.execute("INSERT INTO subscribers (email, name, phone, wa_lid, plan, start_date, end_date, status) VALUES (?,?,?,?,?,?,?,?)",
            (email.lower().strip(), name.strip(), phone.strip(), lid, plan, start, end, "trial"))
        conn.commit()
        perm_id = share_sheet(email)
        if perm_id:
            conn.execute("UPDATE subscribers SET permission_id=? WHERE email=?", (perm_id, email.lower().strip()))
            conn.commit()
        wa_send(phone, f"🎉 *{name}* 试用已开通！\n链接：https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit")
        return True
    except sqlite3.IntegrityError: return False
    finally: conn.close()

def remind_trials():
    print("[sub_mgr/logic.py][cron] 检查试用提醒")
    conn = get_conn()
    now = datetime.utcnow() + MY_TZ_OFFSET
    cutoff = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    trials = conn.execute("SELECT email, name, phone, end_date FROM subscribers WHERE status='trial' AND trial_reminded=0 AND end_date <= ?", (cutoff,)).fetchall()
    for email, name, phone, end_date in trials:
        wa_send(phone, f"⏰ *{name}* 试用快到期了！续费 RM 9.90/月：https://buy.stripe.com/7sY3cu2GOa5u9rp0cI7bW02")
        conn.execute("UPDATE subscribers SET trial_reminded=1 WHERE email=?", (email,))
    conn.commit(); conn.close()

def check_expired():
    now = (datetime.utcnow() + MY_TZ_OFFSET).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[sub_mgr/logic.py][cron] 检查过期 ({now})")
    conn = get_conn()
    overdue = conn.execute("SELECT id, email, name, phone FROM subscribers WHERE status IN ('active','trial') AND end_date <= ?", (now,)).fetchall()
    for sub_id, email, name, phone in overdue:
        conn.execute("UPDATE subscribers SET status='expired' WHERE id=?", (sub_id,))
        revoke_sheet(email)
        wa_send(phone, f"👋 *{name}* 权限已到期。")
    conn.commit(); conn.close()

def renew_subscriber(email, days=30):
    conn = get_conn()
    row = conn.execute("SELECT name, end_date FROM subscribers WHERE email=?", (email.lower().strip(),)).fetchone()
    if not row: return
    name, old_end = row
    now = datetime.utcnow() + MY_TZ_OFFSET
    base = max(now, datetime.strptime(old_end, "%Y-%m-%d %H:%M:%S")) if old_end else now
    new_end = (base + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute("UPDATE subscribers SET end_date=?, status='active' WHERE email=?", (new_end, email.lower().strip()))
    conn.commit(); conn.close()
    if not check_shared(email): share_sheet(email)

def process_form():
    print("[sub_mgr/logic.py][cron] 处理 Form")
    processed = set()
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f: processed = set(json.load(f))
    
    # Simple fallback-less Forms API approach for split file
    svc = get_forms_service()
    try:
        resp = svc.forms().responses().list(formId=FORM_ID, pageSize=50).execute()
        responses = resp.get("responses", [])
        new_count = 0
        for r in responses:
            # Simplified field extraction for brevity in split
            email = next((ans.get('textAnswers', {}).get('answers', [{}])[0].get('value') for ans in r.get('answers', {}).values() if '@' in str(ans)), None)
            if email and email.lower() not in processed:
                if start_trial(email, email.split('@')[0]):
                    processed.add(email.lower())
                    new_count += 1
        if new_count > 0:
            with open(PROCESSED_FILE, "w") as f: json.dump(list(processed), f)
        sync_subscriber_sheet()
        return new_count
    except: return 0

def sync_subscriber_sheet():
    print("[sub_mgr/logic.py][cron] 同步 Sheet")
    conn = get_conn()
    rows = conn.execute("SELECT name, email, phone, plan, start_date, end_date, status FROM subscribers ORDER BY end_date DESC").fetchall()
    conn.close()
    headers = [["姓名", "邮箱", "电话", "方案", "开始", "到期", "状态"]]
    data = [[r[0], r[1], r[2], r[3], r[4][:16], r[5][:16], r[6]] for r in rows]
    sheets_svc, _ = get_sheets_service()
    sheets_svc.spreadsheets().values().update(spreadsheetId=FORM_SHEET_ID, range="订阅状态!A1", valueInputOption="RAW", body={"values": headers + data}).execute()
