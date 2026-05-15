#!/usr/bin/env python3
"""
JB Rentals Auth Server — 微型 HTTP 服务器
支持邮箱+密码登录 和 Google OAuth 登录。
Google 登录自动开通 3 天试用。

端点：
  POST /auth         → {email, password} → {token, name}
  POST /google-auth  → {google_token}    → {token, name, is_new}
  GET  /data         → ?token=xxx → 房源 JSON
  GET  /health       → 健康检查
"""
import json, hashlib, secrets, os, sys, urllib.request
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── 配置 ─────────────────────────────────────────────────
INTERNAL_SHEET_ID = '1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4'
RENTALS_SHEET_ID  = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM'
SUB_SHEET_ID      = '1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg'
SA_KEY = '/home/user/.hermes/google_sa_rental.json'
GOOGLE_CLIENT_ID = '788231638010-v1k56qso1brtia2u9ddqghbbpes4pkm9.apps.googleusercontent.com'
TOKEN_TTL_HOURS = 24
TRIAL_DAYS = 3
PORT = int(os.environ.get('PORT', 8777))

# ── Google Sheets ────────────────────────────────────────
def get_sheets_svc():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_service_account_file(SA_KEY,
        scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return build('sheets', 'v4', credentials=creds)

def read_sheet(sheet_id, range_str):
    svc = get_sheets_svc()
    result = svc.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_str).execute()
    return result.get('values', [])

def append_row(sheet_id, range_str, values):
    svc = get_sheets_svc()
    svc.spreadsheets().values().append(
        spreadsheetId=sheet_id, range=range_str,
        valueInputOption='USER_ENTERED',
        body={'values': [values]}).execute()

# ── 工具函数 ─────────────────────────────────────────────
def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()

def gen_token():
    return secrets.token_urlsafe(36)

def log(msg):
    sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

# ── Google Token 验证 ────────────────────────────────────
def verify_google_id_token(google_token):
    """验证 Google ID token，返回 {email, name, picture} 或 None"""
    try:
        url = f'https://oauth2.googleapis.com/tokeninfo?id_token={google_token}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            # Verify audience
            if data.get('aud') != GOOGLE_CLIENT_ID:
                log(f"Google token audience mismatch: {data.get('aud')}")
                return None
            return {
                'email': data.get('email', '').lower(),
                'name': data.get('name', ''),
                'picture': data.get('picture', ''),
            }
    except Exception as e:
        log(f"Google token verification failed: {e}")
        return None

# ── 用户管理 ─────────────────────────────────────────────
def find_user(email):
    """在 授权用户 Sheet 中查找用户，返回 (row_data, row_index) 或 (None, -1)"""
    email = email.strip().lower()
    rows = read_sheet(INTERNAL_SHEET_ID, '授权用户!A:F')
    for i, row in enumerate(rows[1:], start=1):
        if len(row) < 5:
            continue
        if (row[0] or '').strip().lower() == email:
            return row, i
    return None, -1

def check_user_status(row):
    """检查用户状态，返回 (is_ok, error_msg)"""
    status = (row[4] or '').strip()
    expiry_str = (row[3] or '').strip()

    if status != 'active':
        if status == 'expired':
            return False, '试用已到期，请续费订阅'
        return False, '账号已停用，请联系客服'

    if expiry_str:
        try:
            expiry = datetime.fromisoformat(expiry_str)
            if expiry < datetime.now():
                return False, '试用已到期，请续费订阅'
        except:
            pass

    return True, None

def auto_create_trial(email, name):
    """自动开通 3 天试用，写入 Sheets"""
    now = datetime.now()
    start_str = now.strftime('%Y-%m-%d %H:%M')
    expiry = now + timedelta(days=TRIAL_DAYS)
    expiry_str = expiry.strftime('%Y-%m-%d %H:%M')
    expiry_iso = expiry.isoformat()

    # 1. 授权用户 Sheet（无密码列，Google 登录不需要密码）
    append_row(INTERNAL_SHEET_ID, '授权用户!A:F',
               [email, 'google', name, expiry_iso, 'active', 'Google 自动开通'])

    # 2. 订阅状态 Sheet
    append_row(SUB_SHEET_ID, '订阅状态!A:G',
               [name, email, '', 'standard', start_str, expiry_str, '🟡 试用中'])

    log(f"Auto-created trial for {email} ({name})")

def create_session(email, name):
    """创建登录会话，返回 token"""
    token = gen_token()
    now = datetime.now().isoformat()
    expires = (datetime.now() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    append_row(INTERNAL_SHEET_ID, '登录会话!A:D',
               [token, email, now, expires])
    return token, expires

# ── 邮箱+密码登录 ─────────────────────────────────────────
def verify_login(email, password):
    row, _ = find_user(email)
    if not row:
        return None, '邮箱未授权，请联系客服开通'

    stored_hash = (row[1] or '').strip()
    if stored_hash == 'google':
        return None, '此账号使用 Google 登录，请点击 Google 按钮'

    name = (row[2] or email).strip()
    user_status = (row[4] or '').strip()
    trial_expires_str = (row[3] or '').strip()
    ok, err = check_user_status(row)
    if not ok:
        return None, err

    if sha256(password) != stored_hash:
        return None, '密码错误'

    token, expires = create_session(email, name)
    return {'token': token, 'name': name, 'expires': expires,
            'status': user_status, 'trial_expires': trial_expires_str}, None

# ── Google 登录 ──────────────────────────────────────────
def verify_google_login(google_token):
    """Google 登录，首次自动开通试用。到期用户也可登录（看付费页）"""
    profile = verify_google_id_token(google_token)
    if not profile:
        return None, 'Google 验证失败，请重试'

    email = profile['email']
    name = profile['name']

    row, _ = find_user(email)

    if row:
        # 已有账号 — 不管是否到期，都允许登录
        user_status = (row[4] or '').strip()
        trial_expires_str = (row[3] or '').strip()
        is_new = False
    else:
        # 首次登录 → 自动开通试用
        auto_create_trial(email, name)
        user_status = 'active'
        trial_expires_str = (datetime.now() + timedelta(days=TRIAL_DAYS)).isoformat()
        is_new = True

    token, expires = create_session(email, name)
    return {'token': token, 'name': name, 'expires': expires,
            'is_new': is_new, 'status': user_status, 'trial_expires': trial_expires_str}, None

# ── Token 验证 ───────────────────────────────────────────
def validate_token(token):
    rows = read_sheet(INTERNAL_SHEET_ID, '登录会话!A:D')
    for row in rows[1:]:
        if len(row) < 4: continue
        if row[0] != token: continue
        try:
            expires = datetime.fromisoformat(row[3])
            if expires > datetime.now():
                return True
        except: pass
    return False

def get_user_status(email):
    """获取用户到期信息，用于页面展示"""
    row, _ = find_user(email)
    if not row:
        return None
    name = (row[2] or email).strip()
    expiry_str = (row[3] or '').strip()
    status = (row[4] or '').strip()
    return {'name': name, 'expires': expiry_str, 'status': status}

# ── 房源数据 ─────────────────────────────────────────────
def get_rentals_data():
    rows = read_sheet(RENTALS_SHEET_ID, 'JB Rentals!A:L')
    if len(rows) < 2:
        return {'error': '暂无数据'}

    headers = [h.strip().lower() for h in rows[0]]
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_new = 0
    prop_counter = {}
    listings = []

    for row in rows[1:]:
        r = row + [''] * (len(headers) - len(row))
        d = dict(zip(headers, r))

        phone = d.get('phone', '').strip()
        if not phone or len(phone) < 7: continue

        scraped = d.get('scraped at', '').strip()
        try:
            if datetime.fromisoformat(scraped) >= today_start:
                today_new += 1
        except: pass

        prop = d.get('property name', '').strip()
        if prop:
            prop_counter[prop] = prop_counter.get(prop, 0) + 1

        rent_raw = d.get('rent (rm)', '').strip().lower()
        rent = rent_raw.replace('rm', '').replace('.00', '').replace(' ', '').strip()
        if rent:
            try:
                rent = f"{int(rent.replace(',', '')):,}"
            except: pass

        listings.append({
            'agent': d.get('agent name', '').strip(),
            'property': prop,
            'type': d.get('listing type', '').strip(),
            'property_type': d.get('property type', '').strip(),
            'rooms': d.get('rooms', '').strip(),
            'furnishing': d.get('furnishing', '').strip(),
            'rent': rent,
            'phone': phone,
            'link': d.get('link', '').strip(),
            'remark': d.get('remark', '').strip(),
            'scraped_at': scraped,
            'post_text': d.get('post text', '').strip(),
        })

    listings.sort(key=lambda x: x['scraped_at'], reverse=True)
    top_props = sorted(prop_counter, key=lambda k: prop_counter[k], reverse=True)[:10]

    return {
        'updated_at': now.isoformat(),
        'total': len(listings),
        'today_new': today_new,
        'top_properties': top_props,
        'listings': listings,
    }

# ── HTTP Handler ─────────────────────────────────────────
class AuthHandler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self._cors()
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == '/health':
            self._json({'ok': True})

        elif parsed.path == '/data':
            token = (qs.get('token', [''])[0]).strip()
            if not token:
                self._json({'error': '缺少 token'}, 401)
                return
            if not validate_token(token):
                self._json({'error': '登录已过期，请重新登录'}, 401)
                return
            data = get_rentals_data()
            self._json(data)

        elif parsed.path == '/status':
            token = (qs.get('token', [''])[0]).strip()
            if not token:
                self._json({'error': '缺少 token'}, 401)
                return
            if not validate_token(token):
                self._json({'error': '登录已过期'}, 401)
                return
            # Find email from session
            rows = read_sheet(INTERNAL_SHEET_ID, '登录会话!A:D')
            email = ''
            for row in rows[1:]:
                if row[0] == token:
                    email = row[1]
                    break
            if email:
                status = get_user_status(email)
                self._json(status or {'error': '未找到用户'})
            else:
                self._json({'error': '未找到用户'})

        else:
            self._json({'error': 'Not found'}, 404)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}

        if self.path == '/auth':
            email = body.get('email', '')
            password = body.get('password', '')
            if not email or not password:
                self._json({'error': '邮箱和密码不能为空'}, 400)
                return
            result, err = verify_login(email, password)
            if err:
                self._json({'error': err}, 401)
            else:
                self._json(result)

        elif self.path == '/google-auth':
            google_token = body.get('google_token', '')
            if not google_token:
                self._json({'error': '缺少 Google token'}, 400)
                return
            result, err = verify_google_login(google_token)
            if err:
                self._json({'error': err}, 401)
            else:
                self._json(result)

        else:
            self._json({'error': 'Not found'}, 404)

    def log_message(self, format, *args):
        log(args[0])

def main():
    server = HTTPServer(('127.0.0.1', PORT), AuthHandler)
    print(f'🔐 Auth server running on http://127.0.0.1:{PORT}')
    print(f'   /health  /auth  /google-auth  /data  /status')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.server_close()

if __name__ == '__main__':
    main()
