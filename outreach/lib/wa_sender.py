#!/usr/bin/env python3
"""
WhatsApp Sender — thin wrapper around wa_notify.js CLI.
Talks to wa_daemon.js on localhost:3456 via subprocess.
"""
import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
PROJECT_ROOT = "/home/user/jb-rental-intel"
NOTIFY_CMD = ["node", os.path.join(PROJECT_ROOT, "wa", "wa_notify.js"), "send"]

# ----- 推广文案模板 -----
TEMPLATES = {
    "A": """Hi，我做地产的，最近把 JB 租房群里的 agent 房源全部爬下来整理进一个数据库了——

R&F Cove、Country Garden、TriTower、Paragon 这些盘谁在做什么、什么价钱、电话号码全部一目了然。

要找 cobroke 不用一个个群翻了，看到合适的直接 WhatsApp 对方谈。每天自动更新。

Google 登录即看，3 天免费试用 👇
https://reinocheong.github.io/jb-rental-intel/rentals.html

📧 有问题？smarttenancypro@gmail.com""",

    "B": """Hi，我也是 JB 做 property 的 👋

我手上有一个工具，整理了 JB 5 个 FB 租房群所有 agent 的活跃房源——楼盘名、租金、房型、电话全部有。

简单讲：你想找 cobroke partner，搜楼盘名，5 秒找到谁在卖那个盘，直接 WhatsApp 他谈合作。

Google 一键登录，不用填表，先试 3 天 👇
https://reinocheong.github.io/jb-rental-intel/rentals.html

📧 有问题？smarttenancypro@gmail.com""",

    "C": """Hi，上次提到的 JB 租房工具——给你看实际覆盖：
R&F Cove、Country Garden、TriTower、V Summer、
KSL、Paragon、Suasana、Twin Galaxy 等等

每天 15-20 条新出租帖，自动分类。
有兴趣我发 sample 给你看 👌""",
}


def send_whatsapp(phone: str, template_key: str = "A") -> dict:
    """Send a WhatsApp message via wa_notify.js CLI.
    
    Returns:
        {"ok": True, "phone": phone, "template": template_key}
         or
        {"ok": False, "phone": phone, "error": str}
    """
    msg = TEMPLATES.get(template_key, TEMPLATES["A"])
    phone_clean = str(phone).strip().replace(" ", "").replace("-", "")
    
    # Normalize to international WhatsApp format
    if phone_clean.startswith("+"):
        pass  # already international
    elif phone_clean.startswith("60") and len(phone_clean) >= 10:
        phone_clean = "+" + phone_clean  # 60xxxx → +60xxxx
    elif phone_clean.startswith("65") and len(phone_clean) >= 10:
        phone_clean = "+" + phone_clean  # 65xxxx → +65xxxx (Singapore)
    elif phone_clean.startswith("01") and len(phone_clean) >= 10:
        phone_clean = "+6" + phone_clean  # 01xxxx → +601xxxx (Malaysia)
    elif phone_clean.startswith("0"):
        phone_clean = "+6" + phone_clean  # 0xxxxx → +60xxxxx
    elif len(phone_clean) >= 10:
        phone_clean = "+" + phone_clean  # best effort
    
    # Validate — reject obvious garbage (>15 digits or <8)
    if len(phone_clean.replace("+","")) > 15 or len(phone_clean.replace("+","")) < 8:
        return {"ok": False, "phone": phone, "template": template_key, "error": f"invalid_number: {phone_clean}"}
    
    print(f"  📤 发送给 {phone_clean} (模板 {template_key})...")
    
    try:
        result = subprocess.run(
            NOTIFY_CMD + [phone_clean, msg],
            capture_output=True, text=True, timeout=15,
            cwd=PROJECT_ROOT,
        )
        if result.returncode == 0:
            print(f"  ✅ 已发送")
            return {"ok": True, "phone": phone_clean, "template": template_key}
        else:
            error = result.stderr.strip() or result.stdout.strip()
            print(f"  ❌ 失败: {error}")
            return {"ok": False, "phone": phone_clean, "template": template_key, "error": error}
    except subprocess.TimeoutExpired:
        print(f"  ⏱️ 超时")
        return {"ok": False, "phone": phone_clean, "template": template_key, "error": "timeout"}
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return {"ok": False, "phone": phone_clean, "template": template_key, "error": str(e)}


def check_daemon_alive() -> bool:
    """Check if wa_daemon.js is running on localhost:3456."""
    import socket
    try:
        sock = socket.create_connection(("127.0.0.1", 3456), timeout=3)
        sock.close()
        return True
    except Exception:
        return False
