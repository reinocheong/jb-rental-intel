#!/usr/bin/env python3
"""
导出 JB Rentals Sheet → JSON，供 rentals.html 读取。
只读不写，不碰 Sheet。
"""
import json, os, sys
from datetime import datetime, timezone

SYS_PYTHON = "/home/user/.hermes/hermes-agent/venv/bin/python3"
SA_KEY = "/home/user/.hermes/google_sa_rental.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
RANGE = "JB Rentals!A:L"
OUTPUT = "/home/user/jb-rental-intel/data/rentals.json"

# 列映射
COL_MAP = [
    "agent",       # A
    "property",    # B
    "listing_type",# C
    "property_type",#D
    "rooms",       # E
    "furnishing",  # F
    "rent",        # G
    "phone",       # H
    "link",        # I
    "remark",      # J
    "scraped_at",  # K
    "post_text",   # L
]

def main():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_service_account_file(
        SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    svc = build("sheets", "v4", credentials=creds)

    r = svc.spreadsheets().values().get(
        spreadsheetId=SHEET_ID,
        range=RANGE,
    ).execute()
    rows = r.get("values", [])

    if not rows or len(rows) < 2:
        print("No data rows found")
        payload = {"listings": [], "updated": datetime.now(timezone.utc).isoformat(), "total": 0}
    else:
        header = rows[0]
        data_rows = rows[1:]
        listings = []
        for row in data_rows:
            listing = {}
            for i, key in enumerate(COL_MAP):
                listing[key] = row[i] if i < len(row) else ""
            # 跳过完全空行
            if any(v.strip() for v in listing.values() if v):
                listings.append(listing)

        payload = {
            "listings": listings,
            "total": len(listings),
            "updated": datetime.now(timezone.utc).isoformat(),
        }

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"✅ {len(payload['listings'])} listings → {OUTPUT}")

if __name__ == "__main__":
    main()
