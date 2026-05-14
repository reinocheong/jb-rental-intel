#!/usr/bin/env python3
"""
Export JB Rentals Sheet to JSON for rentals.html viewer.
Read-only — never writes to Sheets.
"""
import json, os, sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from collections import Counter

MY_TZ = ZoneInfo("Asia/Kuala_Lumpur")
PROJECT_ROOT = "/home/user/jb-rental-intel"
SA_KEY = "/home/user/.hermes/google_sa_rental.json"
JB_SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"

def get_sheets_service():
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    creds = Credentials.from_service_account_file(SA_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    return build("sheets", "v4", credentials=creds)

def mask_phone(phone: str) -> str:
    """Mask middle digits: +60123456789 -> +6012***789"""
    p = phone.strip()
    if not p:
        return ""
    if p.startswith("+"):
        digits = p[1:]
        prefix = "+"
    else:
        digits = p
        prefix = ""
    if len(digits) < 7:
        return p
    return f"{prefix}{digits[:4]}***{digits[-3:]}"

def parse_rent(rent_str: str) -> str:
    """Clean rent: 'RM2200' or '2200' -> '2200'"""
    if not rent_str:
        return ""
    r = rent_str.strip().lower().replace("rm", "").replace(".00", "").strip()
    return r

def main():
    svc = get_sheets_service()
    now = datetime.now(MY_TZ)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Read all rows
    resp = svc.spreadsheets().values().get(
        spreadsheetId=JB_SHEET_ID,
        range="JB Rentals!A:L"
    ).execute()
    rows = resp.get("values", [])
    if len(rows) < 2:
        print("No data rows found")
        sys.exit(1)

    headers = [h.strip().lower() for h in rows[0]]
    # Map: Agent Name | Property Name | Listing Type | Property Type | Rooms |
    #       Furnishing | Rent (RM) | Phone | Link | Remark | Scraped At | Post Text

    listings = []
    today_new = 0
    prop_counter = Counter()

    for row in rows[1:]:
        # pad row to header length
        r = row + [""] * (len(headers) - len(row))
        d = dict(zip(headers, r))

        phone = d.get("phone", "").strip()
        if not phone or len(phone) < 7:
            continue

        scraped = d.get("scraped at", "").strip()
        try:
            scraped_dt = datetime.fromisoformat(scraped)
            if scraped_dt >= today_start:
                today_new += 1
        except:
            pass

        prop = d.get("property name", "").strip()
        if prop:
            prop_counter[prop] += 1

        rent_raw = d.get("rent (rm)", "").strip()
        rent = parse_rent(rent_raw)
        if rent:
            try:
                rent = f"{int(rent):,}"
            except:
                pass

        listings.append({
            "agent": d.get("agent name", "").strip(),
            "property": prop,
            "type": d.get("listing type", "").strip(),
            "property_type": d.get("property type", "").strip(),
            "rooms": d.get("rooms", "").strip(),
            "furnishing": d.get("furnishing", "").strip(),
            "rent": rent,
            "phone": phone,
            "link": d.get("link", "").strip(),
            "remark": d.get("remark", "").strip(),
            "scraped_at": scraped,
            "post_text": d.get("post text", "").strip(),
        })

    # Sort newest first
    listings.sort(key=lambda x: x["scraped_at"], reverse=True)

    # Top properties
    top_props = [p for p, _ in prop_counter.most_common(10)]

    output = {
        "updated_at": now.isoformat(),
        "total": len(listings),
        "today_new": today_new,
        "top_properties": top_props,
        "listings": listings,
    }

    os.makedirs(os.path.join(PROJECT_ROOT, "data"), exist_ok=True)
    out_path = os.path.join(PROJECT_ROOT, "data", "rentals.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 导出完成: {len(listings)} 条 ({today_new} 今日新), top: {top_props[:5]}")
    print(f"   → {out_path}")

if __name__ == "__main__":
    main()
