#!/usr/bin/env python3
"""
Smart Tenancy Pro — Subscriber Notifications
Push daily updates (morning/afternoon/evening) to all active subscribers via WhatsApp.

Usage:
  python3 notify_subscribers.py morning    # 9:00 batch
  python3 notify_subscribers.py afternoon  # 13:00 batch
  python3 notify_subscribers.py evening    # 18:00 batch
  python3 notify_subscribers.py test       # Send to yourself only
"""
import sys, os, sqlite3, subprocess, re, json
from datetime import datetime, timezone, timedelta
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

# ── Config ──
PROJECT_ROOT = "/home/user/jb-rental-intel"
SA_KEY_FILE = "/home/user/.hermes/google_sa_key.json"
DB_PATH = os.path.join(PROJECT_ROOT, "subscribers.db")
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
SHEET_NAME = "JB Rentals"
NOTIFY_CMD = ["node", os.path.join(PROJECT_ROOT, "wa", "wa_notify.js"), "send"]
MY_TZ_OFFSET = timedelta(hours=8)

SHEET_URL = "https://reinocheong.github.io/jb-rental-intel/rentals.html"
BOT_LINK = "→ @smarttenancypro_bot"

BOT_PITCH = "需要做租约合同或 stamping？试试我们的 Telegram Bot → @smarttenancypro_bot"

# ── Time-of-day messages ──
MESSAGES = {
    "morning": """🌅 JB Rentals 房源早报
━━━━━━━━━━━━━━━━━━━

📌 昨夜至今新增 {new} 套新帖
🏠 现有房源 {total} 条
👤 活跃 Agent {agents} 人

📊 Google 登录查看：
{SHEET_URL}

{BOT_PITCH}""",

    "afternoon": """☀️ JB Rentals 午间速递
━━━━━━━━━━━━━━━━━━━

🆕 上午新增 {new} 条新房源
🏠 累计 {total} 条

📊 点此查看：
{SHEET_URL}

{BOT_PITCH}""",

    "evening": """📊 JB Rentals 本日总结
━━━━━━━━━━━━━━━━━━━

🆕 今日新增：{new} 条房源帖
🏠 累计房源：{total} 条
👤 活跃 Agent：{agents} 人

📊 登录查看完整列表：
{SHEET_URL}

{BOT_PITCH}""",
}

BATCH_LABELS = {
    "morning": "早报",
    "afternoon": "午间",
    "evening": "日报",
}


# ── Sheet Stats ──
def get_sheet_stats():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_file(SA_KEY_FILE, scopes=scope)
    service = build('sheets', 'v4', credentials=creds)

    # 客户 Sheet — JB Rentals
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_NAME}!A:K").execute()
    rows = result.get('values', [])

    today = datetime.now().replace(tzinfo=timezone.utc) + MY_TZ_OFFSET
    today_str = today.strftime("%Y-%m-%d")

    total = len(rows) - 1  # minus header
    new_today = 0
    for row in rows[1:]:
        if len(row) > 10 and today_str in row[10]:  # Scraped At column
            new_today += 1

    # Agent List
    try:
        sh2 = sheet.values().get(
            spreadsheetId="1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4",
            range="Agent List!A:E"
        ).execute()
        agents_raw = sh2.get('values', [])
        agent_count = len(agents_raw) - 1 if agents_raw else 0
    except Exception:
        agent_count = 0

    return total, new_today, max(agent_count, 0)


# ── Subscribers ──
def get_active_subscribers():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT name, phone FROM subscribers WHERE status IN ('trial', 'active') AND phone != ''"
    )
    subs = cur.fetchall()
    conn.close()
    return subs


# ── Send WhatsApp ──
def send_whatsapp(phone: str, msg: str) -> dict:
    import socket
    try:
        sock = socket.create_connection(("127.0.0.1", 3456), timeout=3)
        sock.close()
    except (socket.timeout, ConnectionRefusedError):
        return {"ok": False, "error": "wa_daemon not running"}

    phone_clean = str(phone).strip().replace(" ", "").replace("-", "")
    if phone_clean.startswith("+"):
        pass
    elif phone_clean.startswith("60") and len(phone_clean) >= 10:
        phone_clean = "+" + phone_clean
    elif phone_clean.startswith("65") and len(phone_clean) >= 10:
        phone_clean = "+" + phone_clean
    elif phone_clean.startswith("01") and len(phone_clean) >= 10:
        phone_clean = "+6" + phone_clean
    elif phone_clean.startswith("0"):
        phone_clean = "+6" + phone_clean
    elif len(phone_clean) >= 10:
        phone_clean = "+" + phone_clean

    if len(phone_clean.replace("+", "")) > 15 or len(phone_clean.replace("+", "")) < 8:
        return {"ok": False, "phone": phone, "error": f"invalid_number: {phone_clean}"}

    try:
        result = subprocess.run(
            NOTIFY_CMD + [phone_clean, msg],
            capture_output=True, text=True, timeout=15,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            return {"ok": True, "phone": phone_clean}
        else:
            return {"ok": False, "phone": phone_clean, "error": result.stderr.strip() or result.stdout.strip()}
    except subprocess.TimeoutExpired:
        return {"ok": False, "phone": phone_clean, "error": "timeout"}
    except Exception as e:
        return {"ok": False, "phone": phone_clean, "error": str(e)}


# ── Main ──
def main():
    if len(sys.argv) < 2:
        print("Usage: python3 notify_subscribers.py <morning|afternoon|evening|test>")
        sys.exit(1)

    batch = sys.argv[1]
    is_test = batch == "test"

    if not is_test and batch not in MESSAGES:
        print(f"Unknown batch: {batch}. Use: morning, afternoon, evening, or test")
        sys.exit(1)

    if is_test:
        batch = "morning"  # use morning template for test

    # Get data
    total, new_today, agent_count = get_sheet_stats()

    if is_test:
        # Send only to user's own number
        test_phone = "60167913913"  # Reino's number from outreach engine
        msg = MESSAGES[batch]
        msg = msg.replace("{new}", str(new_today)).replace("{total}", str(total)).replace("{agents}", str(agent_count))
        msg = msg.replace("{SHEET_URL}", SHEET_URL)
        msg = msg.replace("{BOT_PITCH}", BOT_PITCH)
        msg = msg.replace("{BOT_LINK}", BOT_LINK)
        msg = "[🔬 测试] 订阅通知预览\n\n" + msg

        print(f"🔬 测试模式 — 发送给自己\n")
        print(msg)
        print()
        result = send_whatsapp(test_phone, msg)
        if result.get("ok"):
            print(f"✅ 测试消息已发送到 {test_phone}")
        else:
            print(f"❌ 发送失败: {result.get('error')}")
        return

    # Production: send to all active subscribers
    subscribers = get_active_subscribers()
    if not subscribers:
        print(f"⚠️ 没有活跃订阅用户，跳过 {BATCH_LABELS.get(batch, batch)}")
        return

    msg_template = MESSAGES[batch]
    msg = msg_template.replace("{new}", str(new_today)).replace("{total}", str(total)).replace("{agents}", str(agent_count))
    msg = msg.replace("{SHEET_URL}", SHEET_URL)
    msg = msg.replace("{BOT_PITCH}", BOT_PITCH)
    msg = msg.replace("{BOT_LINK}", BOT_LINK)

    print(f"📢 {BATCH_LABELS.get(batch, batch)} — {len(subscribers)} 位订户")
    print(f"   🆕 今日新增 {new_today} | 🏠 总计 {total} | 👤 {agent_count} Agent")
    print()

    ok = 0
    fail = 0
    for name, phone in subscribers:
        result = send_whatsapp(phone, msg)
        if result.get("ok"):
            print(f"  ✅ {name} ({phone})")
            ok += 1
        else:
            print(f"  ❌ {name} ({phone}): {result.get('error')}")
            fail += 1

    print(f"\n📊 完成: ✅ {ok} 成功, ❌ {fail} 失败, 共 {len(subscribers)} 人")


if __name__ == "__main__":
    main()
