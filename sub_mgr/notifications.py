import os, subprocess
from datetime import datetime

WA_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "wa", "wa_notify.js")

def wa_send(phone, message):
    """Send WhatsApp message via Baileys."""
    print(f"[sub_mgr/notifications.py][whatsapp] 准备发送给 {phone}")
    if not phone: return
    try:
        result = subprocess.run(["node", WA_SCRIPT, "send", phone, message], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"   📤 WhatsApp 已发送给 {phone}")
        else:
            errMsg = result.stderr.strip()[:100]
            with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
                f.write(f"[{datetime.now().isoformat()}] [sub_mgr/notifications.py] [L12] [WASend] -> {errMsg}\n")
    except Exception as e:
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr/notifications.py] [L14] [WASend] -> {e}\n")

def wa_lid(phone):
    if not phone: return ""
    return phone.strip().replace("+", "").replace(" ", "").replace("-", "") + "@s.whatsapp.net"
