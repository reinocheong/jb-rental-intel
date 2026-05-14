#!/usr/bin/env python3
"""
export_rentals_json.py
读取 JB Rentals Sheet → 导出为 data/rentals.json
纯读取，零修改。供 rentals.html 前端使用。
"""
import json, sys, os
from pathlib import Path
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

PROJECT_ROOT = Path("/home/user/jb-rental-intel")
SA_KEY = Path("/home/user/.hermes/google_sa_rental.json")
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
TAB = "JB Rentals"
OUTPUT = PROJECT_ROOT / "data" / "rentals.json"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

def main():
    creds = Credentials.from_service_account_file(str(SA_KEY), scopes=SCOPES)
    svc = build("sheets", "v4", credentials=creds)

    # 读取全部数据
    result = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=f"'{TAB}'!A:L"
    ).execute()
    rows = result.get("values", [])

    if len(rows) < 2:
        print("⚠️  Sheet 数据不足（只有表头或无数据）")
        sys.exit(1)

    headers = rows[0]
    data_rows = rows[1:]

    # 前端需要的字段（排除 Post Text，体积太大对浏览无意义）
    FRONTEND_FIELDS = [
        "Agent Name", "Property Name", "Listing Type", "Property Type",
        "Rooms", "Furnishing", "Rent (RM)", "Phone",
        "Link", "Remark", "Scraped At"
    ]

    listings = []
    for row in data_rows:
        entry = {}
        has_value = False
        for i, h in enumerate(headers):
            val = row[i].strip() if i < len(row) and row[i] else ""
            if h in FRONTEND_FIELDS:
                entry[h] = val
                if val:
                    has_value = True
        # 跳过完全空行
        if has_value:
            listings.append(entry)

    # 统计
    print(f"✅ 读取 {len(data_rows)} 行 → {len(listings)} 条有效房源")

    # 写 JSON（无缩进，最小体积）
    os.makedirs(OUTPUT.parent, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        from datetime import datetime
        json.dump({
            "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total": len(listings),
            "listings": listings,
        }, f, ensure_ascii=False, separators=(",", ":"))

    print(f"📦 已导出 → {OUTPUT} ({OUTPUT.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
