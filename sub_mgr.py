#!/usr/bin/env python3
"""
Smart Tenancy Pro — Subscription Manager
SQLite + Google Sheets/Drive permission automation + WhatsApp notifications.

Usage:
  python3 sub_mgr.py trial <email> <name> <plan> <phone>  # Start 3-day trial
  python3 sub_mgr.py add <email> <name> <plan> [--phone <phone>] [--days 30]
  python3 sub_mgr.py list                     # List all subscribers
  python3 sub_mgr.py check                    # Check trials + expire overdue
  python3 sub_mgr.py remind                   # Remind trial users (day 3)
  python3 sub_mgr.py share <email>            # Share sheet with subscriber
  python3 sub_mgr.py revoke <email>           # Revoke sheet access
  python3 sub_mgr.py renew <email> [--days 30]
  python3 sub_mgr.py status <email>
  python3 sub_mgr.py form-process             # Auto-process new Google Form registrations
"""
import json, sqlite3, os, sys, subprocess
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

# ── Config ──────────────────────────────────────────────
DB_PATH = "/home/user/jb-rental-intel/subscribers.db"
TOKEN_FILE = "/home/user/.hermes/google_token.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
FORM_ID = "1oZTQNl3PF8TOu7RsG2SZeGjx5goT-o2Jy0TL7RlBiIQ"
FORM_SHEET_ID = "1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg"
PROCESSED_FILE = "/home/user/jb-rental-intel/.form_processed.json"
MY_TZ_OFFSET = timedelta(hours=8)  # UTC+8

# ── Database ─────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS subscribers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            wa_lid TEXT DEFAULT '',
            plan TEXT NOT NULL DEFAULT 'basic',
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            permission_id TEXT DEFAULT '',
            trial_reminded INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Migration: add trial_reminded if column missing
    try:
        conn.execute("SELECT trial_reminded FROM subscribers LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE subscribers ADD COLUMN trial_reminded INTEGER DEFAULT 0")
    # Migration: add wa_lid if column missing
    try:
        conn.execute("SELECT wa_lid FROM subscribers LIMIT 1")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE subscribers ADD COLUMN wa_lid TEXT DEFAULT ''")
    conn.commit()
    return conn

def get_conn():
    return sqlite3.connect(DB_PATH)

# ── WhatsApp ─────────────────────────────────────────────
WA_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wa_notify.js")

def wa_lid(phone):
    """Convert phone to WhatsApp JID: 60123456789@s.whatsapp.net"""
    if not phone:
        return ""
    return phone.strip().replace("+", "").replace(" ", "").replace("-", "") + "@s.whatsapp.net"

def wa_send(phone, message):
    """Send WhatsApp message via Baileys."""
    if not phone:
        print("   ⚠️ 无电话号码，跳过 WhatsApp 通知")
        return
    try:
        result = subprocess.run(
            ["node", WA_SCRIPT, "send", phone, message],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"   📤 WhatsApp 已发送给 {phone}")
        else:
            print(f"   ⚠️ WhatsApp 发送失败: {result.stderr.strip()[:100]}")
    except Exception as e:
        print(f"   ⚠️ WhatsApp 异常: {e}")

# ── Google Auth ──────────────────────────────────────────
def get_drive_service():
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    creds = Credentials.from_authorized_user_info(token_data,
        ["https://www.googleapis.com/auth/drive.file"])
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("drive", "v3", credentials=creds)

def get_sheets_service():
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    creds = Credentials.from_authorized_user_info(token_data,
        ["https://www.googleapis.com/auth/spreadsheets",
         "https://www.googleapis.com/auth/drive.file"])
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("sheets", "v4", credentials=creds), build("drive", "v3", credentials=creds)

# ── Sheet Sharing ────────────────────────────────────────
def share_sheet(email):
    """Share Google Sheet with subscriber (view-only)."""
    drive = get_drive_service()
    permission = {
        "type": "user",
        "role": "reader",
        "emailAddress": email
    }
    result = drive.permissions().create(
        fileId=SHEET_ID,
        body=permission,
        sendNotificationEmail=True,
        emailMessage=(
            "🎉 感谢订阅 JB Rental Intel！\n\n"
            "你的 JB 租房数据表已开通，点击以下链接查看：\n"
            f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit\n\n"
            "数据每 30 分钟自动更新，随时打开都是最新的。\n"
            "如有疑问请回复此邮件或 WhatsApp 联系我们。"
        )
    ).execute()
    return result.get("id")

def revoke_sheet(email):
    """Remove subscriber's access to Google Sheet."""
    drive = get_drive_service()
    # List all permissions, find the one for this email
    perms = drive.permissions().list(
        fileId=SHEET_ID,
        fields="permissions(id,emailAddress)"
    ).execute()
    for p in perms.get("permissions", []):
        if p.get("emailAddress", "").lower() == email.lower():
            # Don't revoke owner
            if p.get("role") != "owner":
                drive.permissions().delete(
                    fileId=SHEET_ID,
                    permissionId=p["id"]
                ).execute()
                return p["id"]
    return None

def check_shared(email):
    """Check if email already has access."""
    drive = get_drive_service()
    perms = drive.permissions().list(
        fileId=SHEET_ID,
        fields="permissions(id,emailAddress,role)"
    ).execute()
    for p in perms.get("permissions", []):
        if p.get("emailAddress", "").lower() == email.lower():
            return p.get("role")
    return None

# ── Subscriber CRUD ──────────────────────────────────────
def add_subscriber(email, name, plan="basic", phone="", days=30):
    """Add a new subscriber."""
    conn = get_conn()
    now = datetime.utcnow() + MY_TZ_OFFSET
    start = now.strftime("%Y-%m-%d %H:%M:%S")
    end = (now + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        conn.execute(
            "INSERT INTO subscribers (email, name, phone, plan, start_date, end_date, status) VALUES (?,?,?,?,?,?,?)",
            (email.lower().strip(), name.strip(), phone.strip(), plan, start, end, "active")
        )
        conn.commit()
        
        # Auto-share sheet
        perm_id = share_sheet(email)
        if perm_id:
            conn.execute(
                "UPDATE subscribers SET permission_id=? WHERE email=?",
                (perm_id, email.lower().strip())
            )
            conn.commit()
        
        print(f"✅ {name} ({email}) — {plan} 订阅已开通，到期 {end}")
        print(f"   Google Sheet 已分享（权限ID: {perm_id}）")
        return True
    except sqlite3.IntegrityError:
        print(f"⚠️  {email} 已存在，使用 'renew' 续费")
        return False
    finally:
        conn.close()

def list_subscribers(status=None):
    """List all subscribers."""
    conn = get_conn()
    query = "SELECT name, email, phone, plan, start_date, end_date, status FROM subscribers"
    params = []
    if status:
        query += " WHERE status=?"
        params.append(status)
    query += " ORDER BY end_date DESC"
    
    rows = conn.execute(query, params).fetchall()
    conn.close()
    
    if not rows:
        print("📭 暂无订阅者")
        return
    
    print(f"{'姓名':<12} {'邮箱':<30} {'电话':<14} {'方案':<6} {'开始':<20} {'到期':<20} {'状态'}")
    print("-" * 120)
    for r in rows:
        name, email, phone, plan, start, end, stat = r
        icon = {"active": "🟢", "expired": "🔴", "trial": "🟡"}.get(stat, "⚪")
        print(f"{name:<12} {email:<30} {phone:<14} {plan:<6} {start:<20} {end:<20} {icon} {stat}")

def start_trial(email, name, plan="basic", phone=""):
    """Start 3-day free trial. Auto-shares sheet + sends WhatsApp welcome."""
    conn = get_conn()
    now = datetime.utcnow() + MY_TZ_OFFSET
    start = now.strftime("%Y-%m-%d %H:%M:%S")
    end = (now + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        lid = wa_lid(phone)
        conn.execute(
            "INSERT INTO subscribers (email, name, phone, wa_lid, plan, start_date, end_date, status) VALUES (?,?,?,?,?,?,?,?)",
            (email.lower().strip(), name.strip(), phone.strip(), lid, plan, start, end, "trial")
        )
        conn.commit()
        
        # Auto-share Google Sheet
        perm_id = share_sheet(email)
        if perm_id:
            conn.execute("UPDATE subscribers SET permission_id=? WHERE email=?", (perm_id, email))
            conn.commit()
        
        # WhatsApp welcome message with fingerprint
        sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
        wa_send(phone, 
            f"🎉 *{name}* 你好！\n\n"
            f"Smart Tenancy Pro 市场雷达 3 天试用已开通！\n\n"
            f"📊 数据表链接：\n{sheet_url}\n\n"
            f"数据每 30 分钟自动更新。\n"
            f"试用期到 {end} 截止。\n\n"
            f"💬 有任何问题直接回复此消息即可\n\n"
            f"`Ref: trial-{email}`"
        )
        
        print(f"✅ {name} ({email}) — 3 天试用已开通，到期 {end}")
        return True
    except sqlite3.IntegrityError:
        print(f"⚠️  {email} 已存在")
        return False
    finally:
        conn.close()

def remind_trials():
    """Day 3: remind trial users to subscribe."""
    conn = get_conn()
    now = datetime.utcnow() + MY_TZ_OFFSET
    # Trials that end within 24h and haven't been reminded
    cutoff = (now + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    
    trials = conn.execute(
        "SELECT email, name, phone, end_date FROM subscribers "
        "WHERE status='trial' AND trial_reminded=0 AND end_date <= ?",
        (cutoff,)
    ).fetchall()
    
    if not trials:
        print(f"📭 没有需要提醒的试用用户")
        conn.close()
        return
    
    payment_url = "https://buy.stripe.com/REPLACE_ME"  # TODO: set real Stripe link
    
    for email, name, phone, end_date in trials:
        wa_send(phone,
            f"⏰ *{name}* 试用快到期了！\n\n"
            f"Smart Tenancy Pro 市场雷达试用期到 {end_date} 截止。\n\n"
            f"续费 RM 9.90/月（早鸟价，原价 RM 39.90）：\n"
            f"{payment_url}\n\n"
            f"付款后自动续期，回复我即可 👌"
        )
        conn.execute(
            "UPDATE subscribers SET trial_reminded=1 WHERE email=?",
            (email,)
        )
        print(f"📤 {name} ({phone}) — 试用到期提醒已发送")
    
    conn.commit()
    conn.close()

def check_expired():
    """Check trials + paid subscriptions, expire overdue, revoke access."""
    conn = get_conn()
    now = (datetime.utcnow() + MY_TZ_OFFSET).strftime("%Y-%m-%d %H:%M:%S")
    
    overdue = conn.execute(
        "SELECT id, email, name, phone, permission_id, status FROM subscribers "
        "WHERE status IN ('active','trial') AND end_date <= ?",
        (now,)
    ).fetchall()
    
    if not overdue:
        print(f"✅ [{now}] 没有到期订阅")
        conn.close()
        return
    
    for sub_id, email, name, phone, perm_id, status in overdue:
        conn.execute("UPDATE subscribers SET status='expired' WHERE id=?", (sub_id,))
        revoke_sheet(email)
        
        wa_send(phone,
            f"👋 *{name}* 你好，\n\n"
            f"Smart Tenancy Pro 市场雷达权限已于 {now[:16]} 到期。\n"
            f"Google Sheet 访问权限已自动回收。\n\n"
            f"如需续费，回复此消息即可 🙏"
        )
        
        print(f"🔴 [{now}] {name} ({email}) — {status}已到期，已回收 + WhatsApp 通知")
    
    conn.commit()
    conn.close()

def renew_subscriber(email, days=30):
    """Renew subscription."""
    conn = get_conn()
    row = conn.execute(
        "SELECT name, end_date, status FROM subscribers WHERE email=?",
        (email.lower().strip(),)
    ).fetchone()
    
    if not row:
        print(f"❌ {email} 不存在")
        conn.close()
        return
    
    name, old_end, status = row
    now = datetime.utcnow() + MY_TZ_OFFSET
    
    # Extend from today or from old end date (whichever is later)
    if old_end:
        old_end_dt = datetime.strptime(old_end, "%Y-%m-%d %H:%M:%S")
        base = max(now, old_end_dt)
    else:
        base = now
    
    new_end = (base + timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    
    conn.execute(
        "UPDATE subscribers SET end_date=?, status='active' WHERE email=?",
        (new_end, email.lower().strip())
    )
    conn.commit()
    conn.close()
    
    # Re-share if needed
    if not check_shared(email):
        perm_id = share_sheet(email)
        print(f"   Google Sheet 已重新分享")
    
    print(f"✅ {name} ({email}) 续费 {days} 天，新到期 {new_end}")

def update_wa_lid(lid, fingerprint):
    """Update customer's wa_lid when they reply to fingerprint message."""
    conn = get_conn()
    # Extract email from fingerprint: "Ref: trial-agent@gmail.com"
    # Find subscriber by checking if fingerprint contains email
    import re
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', fingerprint)
    if email_match:
        email = email_match.group(0).lower()
        result = conn.execute(
            "UPDATE subscribers SET wa_lid=? WHERE email=? AND wa_lid=''",
            (lid, email)
        )
        conn.commit()
        if result.rowcount > 0:
            print(f"✅ @lid 已关联: {email} → {lid}")
        else:
            print(f"ℹ️ {email} 已有 @lid 或不存在")
    else:
        print(f"⚠️ 无法从指纹提取邮箱: {fingerprint}")
    conn.close()

def stripe_check_and_renew():
    """Check Stripe for new payments, auto-renew matching subscribers."""
    import subprocess as sp
    result = sp.run(
        ["python3.12", os.path.join(os.path.dirname(os.path.abspath(__file__)), "stripe_checker.py")],
        capture_output=True, text=True, timeout=30
    )
    
    # Parse JSON from output
    payments = []
    if "---JSON---" in result.stdout:
        json_str = result.stdout.split("---JSON---")[1].strip()
        payments = json.loads(json_str)
    
    # Auto-renew each
    for p in payments:
        email = p["email"]
        # Check if subscriber exists
        conn = get_conn()
        row = conn.execute("SELECT name FROM subscribers WHERE email=?", (email,)).fetchone()
        conn.close()
        
        if row:
            # Existing subscriber → renew
            renew_subscriber(email, days=p["days"])
            print(f"   ♻️ {email} 自动续费 {p['days']} 天")
        else:
            # New subscriber → create with appropriate plan
            name = p.get("name", email.split("@")[0])
            phone = ""  # We don't have phone from Stripe
            # Start fresh subscription
            conn = get_conn()
            now = datetime.utcnow() + MY_TZ_OFFSET
            start = now.strftime("%Y-%m-%d %H:%M:%S")
            end = (now + timedelta(days=p["days"])).strftime("%Y-%m-%d %H:%M:%S")
            try:
                lid = wa_lid(phone) if phone else ""
                conn.execute(
                    "INSERT INTO subscribers (email, name, phone, wa_lid, plan, start_date, end_date, status) VALUES (?,?,?,?,?,?,?,?)",
                    (email, name, phone, lid, p["plan"], start, end, "active")
                )
                conn.commit()
                perm_id = share_sheet(email)
                if perm_id:
                    conn.execute("UPDATE subscribers SET permission_id=? WHERE email=?", (perm_id, email))
                    conn.commit()
                print(f"   🆕 {name} ({email}) — Stripe 新订阅 {p['plan']}, 到期 {end}")
            except Exception as e:
                print(f"   ⚠️ {email} 创建失败: {e}")
            finally:
                conn.close()
    
    return payments

def status(email):
    """Check one subscriber's status."""
    conn = get_conn()
    row = conn.execute(
        "SELECT name, email, plan, start_date, end_date, status FROM subscribers WHERE email=?",
        (email.lower().strip(),)
    ).fetchone()
    conn.close()
    
    if not row:
        print(f"❌ {email} 未找到")
        return
    
    name, email, plan, start, end, stat = row
    print(f"  姓名: {name}")
    print(f"  邮箱: {email}")
    print(f"  方案: {plan}")
    print(f"  开始: {start}")
    print(f"  到期: {end}")
    print(f"  状态: {stat}")
    
    # Check if actually shared
    role = check_shared(email)
    print(f"  Sheet权限: {role or '未分享'}")

def process_form():
    """Read Google Form responses, auto-register new trials."""
    # Load processed response IDs
    processed = set()
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            processed = set(json.load(f))
    
    # Get form responses via Forms API
    with open(TOKEN_FILE) as f:
        token_data = json.load(f)
    creds = Credentials.from_authorized_user_info(token_data,
        ["https://www.googleapis.com/auth/forms.responses.readonly"])
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    forms = build("forms", "v1", credentials=creds)
    
    resp = forms.forms().responses().list(formId=FORM_ID).execute()
    responses = resp.get("responses", [])
    
    new_count = 0
    for r in responses:
        rid = r["responseId"]
        if rid in processed:
            continue
        
        # Parse answers: name, WhatsApp, email
        answers = r.get("answers", {})
        
        def get_text(qid):
            a = answers.get(qid, {}).get("textAnswers", {}).get("answers", [{}])
            return a[0].get("value", "") if a else ""
        
        # Question IDs from form creation (index 0, 1, 2)
        # Need to map by looking at the response structure
        qids = list(answers.keys())
        name = get_text(qids[0]) if len(qids) > 0 else ""
        wa = get_text(qids[1]) if len(qids) > 1 else ""
        email = get_text(qids[2]) if len(qids) > 2 else ""
        
        if not email or not name:
            print(f"⚠️ {rid}: 缺少关键字段，跳过")
            continue
        
        print(f"\n🆕 新注册: {name} | {email} | {wa}")
        
        # Start trial
        ok = start_trial(email, name, "standard", wa)
        if ok:
            processed.add(rid)
            new_count += 1
    
    # Save processed IDs
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed), f)
    
    print(f"\n✅ 处理完成: {new_count} 个新注册")
    return new_count

# ── CLI ──────────────────────────────────────────────────
def usage():
    print(__doc__)
    sys.exit(1)

if __name__ == "__main__":
    init_db()  # Ensure DB exists
    
    if len(sys.argv) < 2:
        list_subscribers()
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == "add" and len(sys.argv) >= 4:
        email, name, plan = sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "basic"
        phone = ""
        days = 30
        args = sys.argv[4:]
        i = 0
        while i < len(args):
            if args[i] == "--phone" and i+1 < len(args):
                phone = args[i+1]; i += 2
            elif args[i] == "--days" and i+1 < len(args):
                days = int(args[i+1]); i += 2
            elif i == 0:
                plan = args[i]; i += 1
            else:
                i += 1
        add_subscriber(email, name, plan, phone, days)

    elif cmd == "trial" and len(sys.argv) >= 3:
        email = sys.argv[2]
        name = sys.argv[3] if len(sys.argv) > 3 else ""
        plan = sys.argv[4] if len(sys.argv) > 4 else "basic"
        phone = sys.argv[5] if len(sys.argv) > 5 else ""
        if not name:
            print("用法: python3 sub_mgr.py trial <email> <name> <plan> <phone>")
        else:
            start_trial(email, name, plan, phone)

    elif cmd == "remind":
        remind_trials()

    elif cmd == "stripe-check":
        # Check Stripe for new payments → auto-renew
        payments = stripe_check_and_renew()
        for p in payments:
            print(f"💰 {p['name']} ({p['email']}) — RM {p['amount']:.0f} renewed")

    elif cmd == "update-lid" and len(sys.argv) >= 4:
        # Called by wa_listener.js: update-lid <lid> <fingerprint>
        lid = sys.argv[2]
        fingerprint = sys.argv[3]  # e.g. "Ref: trial-agent@gmail.com"
        update_wa_lid(lid, fingerprint)
    
    elif cmd == "list":
        list_subscribers(sys.argv[2] if len(sys.argv) > 2 else None)
    
    elif cmd == "check":
        check_expired()
    
    elif cmd == "share" and len(sys.argv) >= 3:
        email = sys.argv[2]
        perm_id = share_sheet(email)
        print(f"✅ 已分享给 {email} (权限ID: {perm_id})")
    
    elif cmd == "revoke" and len(sys.argv) >= 3:
        email = sys.argv[2]
        perm_id = revoke_sheet(email)
        print(f"{'✅ 已回收' if perm_id else '⚠️ 未找到权限'} {email}")
    
    elif cmd == "renew" and len(sys.argv) >= 3:
        email = sys.argv[2]
        days = 30
        if len(sys.argv) > 3 and sys.argv[3] == "--days" and len(sys.argv) > 4:
            days = int(sys.argv[4])
        renew_subscriber(email, days)
    
    elif cmd == "status" and len(sys.argv) >= 3:
        status(sys.argv[2])
    
    elif cmd == "form-process":
        process_form()
    
    else:
        usage()
