from .sheet_reader import get_sheets_service
from datetime import datetime

INTERNAL_SHEET_ID = "1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4"

def get_outreach_records():
    svc = get_sheets_service()
    res = svc.spreadsheets().values().get(spreadsheetId=INTERNAL_SHEET_ID, range="推广记录!A:H").execute()
    values = res.get("values", [])
    if not values: return []
    headers = [h.lower() for h in values[0]]
    records = []
    for row in values[1:]:
        records.append(dict(zip(headers, row + ['']*(len(headers)-len(row)))))
    return records

def append_outreach_record(data):
    svc = get_sheets_service()
    row = [data.get('phone'), data.get('agent'), data.get('property'), data.get('template'), datetime.now().isoformat(), data.get('status', '已发送'), '', '']
    svc.spreadsheets().values().append(spreadsheetId=INTERNAL_SHEET_ID, range="推广记录!A:H", valueInputOption="RAW", body={"values": [row]}).execute()

def get_subscribed_phones():
    svc = get_sheets_service()
    res = svc.spreadsheets().values().get(spreadsheetId="1zLOyuRbZnycvD0tc4UPLSoR3mfClwkiDOPw3W-v-gXg", range="订阅状态!C:C").execute()
    return [r[0] for r in res.get("values", [])[1:] if r]
