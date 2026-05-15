#!/usr/bin/env python3
"""
JB Rentals Auth Server — 微型 HTTP 服务器
提供登录验证和数据接口，用 Google Sheets 做用户数据库。

端点：
  POST /auth     → {email, password} → {token, name} 或 {error}
  GET  /data     → ?token=xxx → 房源 JSON 或 {error}
  GET  /health   → 健康检查
"""
import json, hashlib, secrets, os, sys
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ── 配置 ─────────────────────────────────────────────────
INTERNAL_SHEET_ID = '1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4'
RENTALS_SHEET_ID  = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM'
SA_KEY = '/home/user/.hermes/google_sa_rental.json'
TOKEN_TTL_HOURS = 24
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

# ── 登录验证 ─────────────────────────────────────────────
def verify_login(email, password):
    email = email.strip().lower()
    rows = read_sheet(INTERNAL_SHEET_ID, '授权用户!A:F')
    for row in rows[1:]:
        if len(row) < 5: continue
        row_email = (row[0] or '').strip().lower()
        if row_email != email: continue

        stored_hash = (row[1] or '').strip()
        name = (row[2] or email).strip()
        status = (row[4] or '').strip()
        expiry_str = (row[3] or '').strip()

        if status != 'active':
            return None, '账号已停用，请联系客服'
        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str)
                if expiry < datetime.now():
                    return None, '账号已过期，请联系续费'
            except: pass

        if sha256(password) != stored_hash:
            return None, '密码错误'

        # Generate session token
        token = gen_token()
        now = datetime.now().isoformat()
        expires = (datetime.now() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
        append_row(INTERNAL_SHEET_ID, '登录会话!A:D',
                   [token, email, now, expires])
        return {'token': token, 'name': name, 'expires': expires}, None

    return None, '邮箱未授权，请联系客服开通'

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

        else:
            self._json({'error': 'Not found'}, 404)

    def do_POST(self):
        if self.path == '/auth':
            length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(length))
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

        else:
            self._json({'error': 'Not found'}, 404)

    def log_message(self, format, *args):
        # 简洁日志
        sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {args[0]}\n")

def main():
    server = HTTPServer(('127.0.0.1', PORT), AuthHandler)
    print(f'🔐 Auth server running on http://127.0.0.1:{PORT}')
    print(f'   /health  /auth (POST)  /data?token=xxx (GET)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down...')
        server.server_close()

if __name__ == '__main__':
    main()
