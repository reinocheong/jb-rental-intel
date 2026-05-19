import sqlite3, os
from datetime import timedelta

DB_PATH = "/home/user/jb-rental-intel/subscribers.db"

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    print("[sub_mgr/db.py][init] 初始化数据库")
    conn = get_conn()
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
    try: conn.execute("SELECT trial_reminded FROM subscribers LIMIT 1")
    except: conn.execute("ALTER TABLE subscribers ADD COLUMN trial_reminded INTEGER DEFAULT 0")
    try: conn.execute("SELECT wa_lid FROM subscribers LIMIT 1")
    except: conn.execute("ALTER TABLE subscribers ADD COLUMN wa_lid TEXT DEFAULT ''")
    conn.commit()
    return conn
