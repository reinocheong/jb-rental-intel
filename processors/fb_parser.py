#!/usr/bin/env python3
"""
Facebook JB Rental Parser → Google Sheets
Reads raw JSON, extracts structured fields, appends to Google Sheets.
"""
import json, re, os, sys
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

# Import local libs
from lib.phone_utils import normalize_phone
from lib.text_cleaner import clean_post_text
from lib.filters import is_comment_thread, is_rental_post, is_looking_for_rental
from lib.property_data import is_valid_property_name
from lib.extractors import (
    extract_listing_type, extract_property_name, extract_property_type,
    extract_rooms, extract_rent, extract_furnishing, extract_remark, format_scraped_at
)
from lib.sheet_writer import get_sheets_service, read_sheet, append_rows, update_range

# --- Config ---
RAW_JSON = "/home/user/fb_data/fb_posts_raw.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"
SHEET_NAME = "JB Rentals"
SA_KEY_FILE = "/home/user/.hermes/google_sa_key.json"
HEADERS = ["Agent Name", "Property Name", "Listing Type", "Property Type", "Rooms", "Furnishing", "Rent (RM)", "Phone", "Link", "Remark", "Scraped At", "Post Text"]

def parse_post(post):
    """Parse one raw post into structured fields."""
    raw_text = post.get("text", "")
    text = clean_post_text(raw_text)
    agent = post.get("agent_name", "")
    phone = normalize_phone(post.get("phone", ""))
    link = post.get("link", "")
    scraped_at = post.get("scraped_at", "")
    group_name = post.get("group_name", "")

    _fb_name = re.compile(r'^[A-Z][a-z]{3,}[A-Z][a-z]{3,}\d*$')
    if not agent or _fb_name.match(agent):
        m = re.match(r'^([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)', text)
        if m and not _fb_name.match(m.group(1)): agent = m.group(1)
        else:
            m = re.match(r'^([\u4e00-\u9fff]{2,4})', text)
            if m: agent = m.group(1)
        if agent and _fb_name.match(agent): agent = ''

    prop_name = extract_property_name(text)
    if prop_name and not is_valid_property_name(prop_name): prop_name = ""
    listing_type = extract_listing_type(text)
    prop_type = extract_property_type(text)
    rooms = extract_rooms(text)
    furnishing = extract_furnishing(text)
    
    rent = ""
    price_remark = ""
    if listing_type == "出租": rent = extract_rent(raw_text) or extract_rent(text)
    else:
        m = re.search(r'(?:RM|rm)\s*(\d[\d,.]{2,6})', raw_text)
        if m:
            try: price_remark = f"售价: RM{int(m.group(1).replace(',','')):,}"
            except: price_remark = f"售价: RM{m.group(1)}"
    
    remark = extract_remark(text, prop_name, prop_type, rooms)
    if price_remark: remark = f"{price_remark}; {remark}" if remark else price_remark
    if group_name and group_name not in remark: remark = f"[{group_name}] {remark}".strip()

    return {"agent": agent, "property": prop_name, "listing_type": listing_type, "type": prop_type, "rooms": rooms, "furnishing": furnishing, "rent": rent, "phone": phone, "link": link, "remark": remark, "scraped_at": format_scraped_at(scraped_at), "post_text": text}

def build_sheets():
    """Main orchestration for parsing and sheet writing."""
    print("[processors/fb_parser.py][main] 开始")
    service = get_sheets_service(SA_KEY_FILE)
    
    raw_posts = []
    if os.path.exists(RAW_JSON):
        with open(RAW_JSON, "r") as f: raw_posts = json.load(f)
    print(f"[processors/fb_parser.py][processing] 加载了 {len(raw_posts)} 条原始数据")

    parsed, seen, skipped = [], set(), {"comment_thread": 0, "non_rental": 0, "looking": 0}
    for post in raw_posts:
        raw_text = post.get("text", "")
        cleaned = clean_post_text(raw_text)
        if is_looking_for_rental(cleaned) or is_looking_for_rental(raw_text):
            skipped["looking"] += 1; continue
        if not is_rental_post(raw_text):
            skipped["non_rental"] += 1; continue
        if is_comment_thread(raw_text):
            skipped["comment_thread"] += 1; continue
        row = parse_post(post)
        if row["link"] in seen: continue
        seen.add(row["link"]); parsed.append(row)

    print(f"[processors/fb_parser.py][processing] 解析完成，待去重条数: {len(parsed)}")

    existing_links, existing_phones, existing_texts = set(), set(), set()
    try:
        values = read_sheet(service, SHEET_ID, f"{SHEET_NAME}!A:L")
        if values:
            for row in values[1:]:
                if len(row) > 8 and row[8]: existing_links.add(row[8])
                if len(row) > 7 and row[7]:
                    for p in str(row[7]).split(','):
                        if p.strip(): existing_phones.add(p.strip())
                key = f"{row[1] if len(row)>1 else ''}|{row[3] if len(row)>3 else ''}|{row[4] if len(row)>4 else ''}|{row[6] if len(row)>6 else ''}"
                if key.strip('|'): existing_texts.add(key)
        total_rows = len(values)
    except Exception as e:
        print(f"[processors/fb_parser.py][error] 读取失败: {e}")
        total_rows = 0

    unique_parsed = []
    for rd in parsed:
        if rd["link"] in existing_links: continue
        if rd["phone"] and any(p.strip() in existing_phones for p in rd["phone"].split(',') if p.strip()): continue
        key = f"{rd['property']}|{rd['type']}|{rd['rooms']}|{rd['rent']}"
        if key.strip('|') and key in existing_texts: continue
        unique_parsed.append(rd)
        if rd["link"]: existing_links.add(rd["link"])
        if rd["phone"]:
            for p in rd["phone"].split(','):
                if p.strip(): existing_phones.add(p.strip())
        if key.strip('|'): existing_texts.add(key)

    if total_rows == 0:
        update_range(service, SHEET_ID, f"{SHEET_NAME}!A1:L1", [HEADERS])
        total_rows = 1

    new_rows = 0
    if unique_parsed:
        rows_to_write = [[rd["agent"], rd["property"], rd["listing_type"], rd["type"], rd["rooms"], rd["furnishing"], rd["rent"], rd["phone"], rd["link"], rd["remark"], rd["scraped_at"], rd["post_text"]] for rd in unique_parsed]
        append_rows(service, SHEET_ID, f"{SHEET_NAME}!A:{chr(64+len(HEADERS))}", rows_to_write)
        new_rows = len(rows_to_write)

    print(f"[processors/fb_parser.py][main] 结束，新增 {new_rows} 条")
    return {"total_rows": total_rows + new_rows, "new_rows": new_rows, "skipped": skipped, "parsed": unique_parsed}

if __name__ == "__main__":
    res = build_sheets()
    print(json.dumps({"total": res["total_rows"], "new": res["new_rows"], "skipped": res["skipped"]}, ensure_ascii=False, indent=2))
