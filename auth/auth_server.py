#!/usr/bin/env python3
import json, hashlib, secrets, os, sys, urllib.request, sqlite3
from datetime import datetime, timezone, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from .lib.sheet_ops import read_sheet, append_row

INTERNAL_SHEET_ID = '1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4'
RENTALS_SHEET_ID  = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM'
SUB_SHEET_ID      = '1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg'
GOOGLE_CLIENT_ID = '788231638010-v1k56qso1brtia2u9ddqghbbpes4pkm9.apps.googleusercontent.com'
TOKEN_TTL_HOURS, TRIAL_DAYS, PORT = 24, 3, int(os.environ.get('PORT', 8777))

def sha256(s): return hashlib.sha256(s.encode()).hexdigest()
def gen_token(): return secrets.token_urlsafe(36)
def log_msg(msg): sys.stderr.write(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")

def find_user(email):
    rows = read_sheet(INTERNAL_SHEET_ID, '授权用户!A:F')
    for i, row in enumerate(rows[1:], start=1):
        if len(row) >= 5 and (row[0] or '').strip().lower() == email.strip().lower(): return row, i
    return None, -1

def create_session(email, name):
    token = gen_token()
    now, expires = datetime.now().isoformat(), (datetime.now() + timedelta(hours=TOKEN_TTL_HOURS)).isoformat()
    append_row(INTERNAL_SHEET_ID, '登录会话!A:D', [token, email, now, expires])
    return token, expires

def get_rentals_data():
    rows = read_sheet(RENTALS_SHEET_ID, 'JB Rentals!A:L')
    if len(rows) < 2: return {'error': '暂无数据'}
    headers = [h.strip().lower() for h in rows[0]]
    listings = []
    for row in rows[1:]:
        d = dict(zip(headers, row + ['']*(len(headers)-len(row))))
        if not d.get('phone'): continue
        listings.append({'agent': d.get('agent name'), 'property': d.get('property name'), 'rent': d.get('rent (rm)'), 'phone': d.get('phone'), 'link': d.get('link'), 'scraped_at': d.get('scraped at')})
    return {'listings': listings, 'total': len(listings)}

class AuthHandler(BaseHTTPRequestHandler):
    def _json(self, data, status=200):
        body = json.dumps(data).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type', 'application/json'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == '/health': self._json({'ok': True})
        elif '/data' in self.path: self._json(get_rentals_data())
        else: self._json({'error': 'Not found'}, 404)
    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length > 0 else {}
        if self.path == '/auth':
            email, password = body.get('email'), body.get('password')
            row, _ = find_user(email)
            if row and row[1] == sha256(password):
                token, exp = create_session(email, row[2])
                self._json({'token': token, 'name': row[2], 'expires': exp})
            else: self._json({'error': '验证失败'}, 401)
        else: self._json({'error': 'Not found'}, 404)

def main():
    server = HTTPServer(('127.0.0.1', PORT), AuthHandler)
    print(f'🔐 Auth server running on {PORT}'); server.serve_forever()

if __name__ == '__main__': main()
