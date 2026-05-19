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
from google.oauth2.service_account import Credentials

# ── Config ──────────────────────────────────────────────
SA_KEY_FILE = "/home/user/.hermes/google_sa_key.json"
DB_PATH = "/home/user/jb-rental-intel/subscribers.db"
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
WA_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wa", "wa_notify.js")

def wa_lid(phone):
    """Convert phone to WhatsApp JID: 60123456789@s.whatsapp.net"""
    if not phone:
        return ""
    return phone.strip().replace("+", "").replace(" ", "").replace("-", "") + "@s.whatsapp.net"

def wa_send(phone, message):
    """Send WhatsApp message via Baileys."""
    print(f"[sub_mgr.py][whatsapp] 准备发送给 {phone}")
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
            errMsg = result.stderr.strip()[:100]
            print(f"   ⚠️ WhatsApp 发送失败: {errMsg}")
            with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
                f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L87] [WASend] -> {errMsg}\n")
    except Exception as e:
        print(f"   ⚠️ WhatsApp 异常: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L90] [WASend] -> {e}\n")

# ── Google Auth ──────────────────────────────────────────
def get_drive_service():
    print("[sub_mgr.py][google] 初始化 Drive 服务")
    creds = Credentials.from_service_account_file(SA_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)

def get_sheets_service():
    print("[sub_mgr.py][google] 初始化 Sheets 服务")
    creds = Credentials.from_service_account_file(SA_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"])
    return build("sheets", "v4", credentials=creds), build("drive", "v3", credentials=creds)

def get_forms_service():
    """Get Forms API service (for reading form responses directly)."""
    print("[sub_mgr.py][google] 初始化 Forms 服务")
    creds = Credentials.from_service_account_file(SA_KEY_FILE,
        scopes=["https://www.googleapis.com/auth/forms.responses.readonly",
                "https://www.googleapis.com/auth/forms.body"])
    return build("forms", "v1", credentials=creds)

# ── Sheet Sharing ────────────────────────────────────────
def share_sheet(email):
    """Share Google Sheet with subscriber (view-only)."""
    print(f"[sub_mgr.py][google] 分享 Sheet 给 {email}")
    drive = get_drive_service()
    permission = {
        "type": "user",
        "role": "reader",
        "emailAddress": email
    }
    try:
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
    except Exception as e:
        print(f"   ⚠️ 分享失败: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L133] [ShareSheet] -> {e}\n")
        return None

def revoke_sheet(email):
    """Remove subscriber's access to Google Sheet."""
    print(f"[sub_mgr.py][google] 回收 {email} 的权限")
    drive = get_drive_service()
    # List all permissions, find the one for this email
    try:
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
    except Exception as e:
        print(f"   ⚠️ 回收失败: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L153] [RevokeSheet] -> {e}\n")
    return None

def check_shared(email):
    """Check if email already has access."""
    print(f"[sub_mgr.py][google] 检查 {email} 是否已有权限")
    drive = get_drive_service()
    try:
        perms = drive.permissions().list(
            fileId=SHEET_ID,
            fields="permissions(id,emailAddress,role)"
        ).execute()
        for p in perms.get("permissions", []):
            if p.get("emailAddress", "").lower() == email.lower():
                return p.get("role")
    except Exception as e:
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L165] [CheckShared] -> {e}\n")
    return None

# ── Subscriber CRUD ──────────────────────────────────────
def add_subscriber(email, name, plan="basic", phone="", days=30):
    """Add a new subscriber."""
    print(f"[sub_mgr.py][db] 添加订阅: {email}")
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
    except Exception as e:
        print(f"   ⚠️ 添加失败: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L197] [AddSub] -> {e}\n")
        return False
    finally:
        conn.close()

def list_subscribers(status=None):
    """List all subscribers."""
    print(f"[sub_mgr.py][db] 列出订阅 (status={status})")
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
    print(f"[sub_mgr.py][db] 开启试用: {email}")
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
            conn.execute("UPDATE subscribers SET permission_id=? WHERE email=?", (perm_id, email.lower().strip()))
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
    except Exception as e:
        print(f"   ⚠️ 开启试用失败: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L261] [StartTrial] -> {e}\n")
        return False
    finally:
        conn.close()

def remind_trials():
    """Day 3: remind trial users to subscribe."""
    print("[sub_mgr.py][cron] 检查需要提醒的试用用户")
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
    
    payment_url = "https://buy.stripe.com/7sY3cu2GOa5u9rp0cI7bW02"
    
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
    now_dt = datetime.utcnow() + MY_TZ_OFFSET
    now = now_dt.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[sub_mgr.py][cron] 检查过期订阅 ({now})")
    conn = get_conn()
    
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
    print(f"[sub_mgr.py][db] 续费订阅: {email}")
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
        try:
            old_end_dt = datetime.strptime(old_end, "%Y-%m-%d %H:%M:%S")
            base = max(now, old_end_dt)
        except:
            base = now
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
    print(f"[sub_mgr.py][db] 更新 wa_lid: {fingerprint} → {lid}")
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
    print("[sub_mgr.py][cron] 检查 Stripe 付款")
    import subprocess as sp
    try:
        result = sp.run(
            ["python3.12", os.path.join(os.path.dirname(os.path.abspath(__file__)), "stripe_checker.py")],
            capture_output=True, text=True, timeout=30
        )
    except Exception as e:
        print(f"   ⚠️ Stripe Checker 失败: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L404] [StripeCheck] -> {e}\n")
        return []
    
    # Parse JSON from output
    payments = []
    if "---JSON---" in result.stdout:
        json_str = result.stdout.split("---JSON---")[1].strip()
        payments = json.loads(json_str)
    
    print(f"   收到 {len(payments)} 笔新付款")

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
                with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L445] [StripeAddSub] -> {e}\n")
            finally:
                conn.close()
    
    return payments

def status(email):
    """Check one subscriber's status."""
    print(f"[sub_mgr.py][db] 查状态: {email}")
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
    """Read Google Form responses via Forms API directly, auto-register new trials.
    
    Does NOT require the form to be linked to a Sheet — reads responses
    from the Forms API responses endpoint. Deduplicates by email across runs.
    """
    print("[sub_mgr.py][cron] 处理 Google Form 新回复")
    import re
    
    # Load previously processed emails
    processed = set()
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            processed = set(json.load(f))
    
    # Step 1: Try Forms API directly; fall back to linked Sheet on 403
    forms_svc = get_forms_service()
    try:
        form = forms_svc.forms().get(formId=FORM_ID).execute()
        use_forms_api = True
    except Exception as e:
        print(f"   ⚠️ Forms API 不可用 ({e}), 回退到 Sheet 读取")
        use_forms_api = False

    if use_forms_api:
        # Build questionId -> title/type map
        q_map = {}
        for item in form.get("items", []):
            qi = item.get("questionItem", {}).get("question", {})
            qid = qi.get("questionId")
            if qid:
                q_map[qid] = {
                    "title": item.get("title", ""),
                    "type": "text" if "textQuestion" in qi else "choice" if "choiceQuestion" in qi else "other"
                }

        print(f"📋 表单字段: {list(q_map.values())}")

        # Step 2: Fetch all responses
        try:
            resp = forms_svc.forms().responses().list(
                formId=FORM_ID,
                pageSize=500
            ).execute()
            responses = resp.get("responses", [])
        except Exception as e:
            print(f"   ⚠️ 获取回复失败: {e}")
            with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
                f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L517] [ListResponses] -> {e}\n")
            responses = []

        if not responses:
            print("📭 表单暂无回复")
            sync_subscriber_sheet()
            return 0

        print(f"📨 收到 {len(responses)} 条回复")

        new_count = 0
        for r in responses:
            answers = r.get("answers", {})
            resp_id = r.get("responseId", "unknown")

            # Extract fields by matching question titles
            email, name, phone = "", "", ""

            for qid, answer_data in answers.items():
                q_info = q_map.get(qid, {})
                title = q_info.get("title", "").lower()

                # Get text value
                text_val = ""
                ta = answer_data.get("textAnswers", {})
                ans_list = ta.get("answers", [])
                if ans_list:
                    text_val = ans_list[0].get("value", "")

                # Match by title keywords
                if any(kw in title for kw in ["email", "邮箱", "mail"]):
                    email = text_val.strip()
                elif any(kw in title for kw in ["名字", "姓名", "name", "nama"]):
                    name = text_val.strip()
                elif any(kw in title for kw in ["whatsapp", "电话", "手机", "phone", "tel", "wa"]):
                    phone = text_val.strip()

            # Clean phone
            phone = re.sub(r'[^\d+]', '', phone)

            if not email or "@" not in email:
                print(f"   ⏭️ 跳过 (无效邮箱): {email}")
                continue

            # Dedup by email
            if email.lower() in processed:
                continue

            if not name:
                name = email.split("@")[0]

            print(f"\n🆕 新注册 ({resp_id[:8]}...): {name} | {email} | {phone}")

            # Start trial
            ok = start_trial(email, name, "standard", phone)
            if ok:
                processed.add(email.lower())
                new_count += 1
    else:
        # Fallback: read from linked Google Sheet
        try:
            sheets_svc, _ = get_sheets_service()
            result = sheets_svc.spreadsheets().values().get(
                spreadsheetId=FORM_SHEET_ID,
                range="第 1 张表单回复"
            ).execute()
            values = result.get("values", [])
        except Exception as e:
            print(f"   ⚠️ Sheet 读取失败: {e}")
            with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
                f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L586] [SheetRead] -> {e}\n")
            values = []

        if not values:
            print("📭 表单回复 Sheet 为空")
            sync_subscriber_sheet()
            return 0

        headers = values[0]
        print(f"📋 Sheet Headers: {headers}")

        # Find column indices
        email_col = name_col = phone_col = None
        for i, h in enumerate(headers):
            hl = h.lower()
            if any(kw in hl for kw in ["email", "邮箱", "mail"]):
                email_col = i
            elif any(kw in hl for kw in ["名字", "姓名", "name", "nama"]):
                name_col = i
            elif any(kw in hl for kw in ["whatsapp", "电话", "手机", "phone", "tel", "wa"]):
                phone_col = i

        print(f"   Email col: {email_col}, Name col: {name_col}, Phone col: {phone_col}")
        print(f"📨 收到 {len(values)-1} 条回复")

        new_count = 0
        for row_num, row in enumerate(values[1:], start=2):
            email = row[email_col].strip() if email_col is not None and email_col < len(row) else ""
            name = row[name_col].strip() if name_col is not None and name_col < len(row) else ""
            phone = row[phone_col].strip() if phone_col is not None and phone_col < len(row) else ""
            phone = re.sub(r'[^\d+]', '', phone)

            if not email or "@" not in email:
                print(f"   ⏭️ Row {row_num}: 无效邮箱 ({email})")
                continue

            if email.lower() in processed:
                continue

            if not name:
                name = email.split("@")[0]

            print(f"\n🆕 Row {row_num}: {name} | {email} | {phone}")
            ok = start_trial(email, name, "standard", phone)
            if ok:
                processed.add(email.lower())
                new_count += 1
    
    # Save processed emails
    if new_count > 0:
        with open(PROCESSED_FILE, "w") as f:
            json.dump(list(processed), f)
    
    # Sync subscription status to Form Response Sheet
    sync_subscriber_sheet()
    
    print(f"\n✅ 处理完成: {new_count} 个新注册")
    return new_count

def sync_subscriber_sheet():
    """Update 「订阅状态」sheet in the Form Response spreadsheet."""
    print("[sub_mgr.py][cron] 同步订阅状态到 Sheet")
    import sqlite3
    try:
        db = sqlite3.connect(DB_PATH)
        rows = db.execute("""
            SELECT name, email, phone, plan, start_date, end_date, status 
            FROM subscribers ORDER BY end_date DESC
        """).fetchall()
        db.close()
        
        headers = [["姓名", "邮箱", "电话", "方案", "开始", "到期", "状态"]]
        data = [[r[0], r[1], r[2], r[3], r[4][:16], r[5][:16], 
            {"trial":"🟡 试用中","active":"🟢 已付费","expired":"🔴 已过期"}.get(r[6], r[6])] 
            for r in rows]
        
        sheets_svc, _drive_svc = get_sheets_service()
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=FORM_SHEET_ID,
            range="订阅状态!A1",
            valueInputOption="RAW",
            body={"values": headers + data}
        ).execute()
        print("   ✅ 同步完成")
    except Exception as e:
        print(f"   ⚠️ 订阅状态同步失败: {e}")
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr.py] [L668] [SyncSheet] -> {e}\n")

# ── CLI ──────────────────────────────────────────────────
def usage():
    print(__doc__)
    sys.exit(1)

if __name__ == "__main__":
    print("[sub_mgr.py][main] 开始")
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
        if perm_id:
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
    
    elif cmd == "sync-sheets":
        sync_subscriber_sheet()
    
    else:
        usage()
    print("[sub_mgr.py][main] 结束")
