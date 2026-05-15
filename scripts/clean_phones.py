#!/usr/bin/env python3
"""
一次性清洗 JB Rentals Sheet Phone (H) 列。
干跑模式: python3 scripts/clean_phones.py
写入模式: python3 scripts/clean_phones.py --apply
"""
import sys, re, json, os
from collections import defaultdict
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SA_KEY = '/home/user/.hermes/google_sa_rental.json'
SHEET_ID = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM'

# ─── normalization ──────────────────────────────────────

def normalize_phone(raw: str) -> str | None:
    """Return +60xxxxxxxxx if valid Malaysian/Singapore number, else None."""
    # Strip all non-digits except +
    s = raw.strip()
    has_plus = s.startswith('+')
    digits = re.sub(r'\D', '', s)
    
    # Masked numbers — discard
    if '*' in s or len(digits) < 8 or len(digits) > 15:
        return None
    
    # Already international: +60 / +65
    if has_plus:
        if digits.startswith('60') and 10 <= len(digits) <= 13:
            return '+' + digits
        if digits.startswith('65') and 10 <= len(digits) <= 12:
            return '+' + digits
        return None
    
    # Local Malaysian: 01x → +60
    if re.match(r'^01\d', s) and 10 <= len(digits) <= 11:
        return '+60' + digits[1:]  # 0127676396 → +60127676396
    
    # No prefix: 60xxxx → +60
    if digits.startswith('60') and 10 <= len(digits) <= 13:
        return '+' + digits
    
    # Singapore local: 8xxx / 9xxx 8-digit
    if re.match(r'^[89]\d{7}$', digits):
        return '+65' + digits
    
    return None

def clean_phone_cell(raw: str) -> str | None:
    """Extract the first valid normalized number from a cell."""
    if not raw or not raw.strip():
        return None
    
    # Split on common separators
    parts = re.split(r'[,;，；/\s]+', raw.strip())
    
    seen = set()  # deduplicate by normalized digits
    candidates = []
    
    for p in parts:
        p = p.strip()
        if not p:
            continue
        norm = normalize_phone(p)
        if norm is None:
            continue
        digits = re.sub(r'\D', '', norm)
        if digits not in seen:
            seen.add(digits)
            candidates.append(norm)
    
    if not candidates:
        return None
    
    # Return first valid number
    return candidates[0]


# ─── main ───────────────────────────────────────────────

def main():
    dry_run = '--apply' not in sys.argv
    
    creds = Credentials.from_service_account_file(SA_KEY, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    svc = build('sheets', 'v4', credentials=creds)
    
    # Read all phone data
    r = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="'JB Rentals'!A1:H").execute()
    rows = r.get('values', [])
    header = rows[0]
    
    changes = []  # (row_num_1based, agent, old_phone, new_phone, action)
    
    for i, row in enumerate(rows[1:], start=2):
        # Safely get cells
        agent = row[0].strip() if len(row) > 0 and row[0] else ''
        phone_raw = ''
        if len(row) > 7:
            phone_raw = row[7].strip()
        
        if not phone_raw:
            continue
        
        cleaned = clean_phone_cell(phone_raw)
        
        if cleaned is None:
            # No valid number — clear the cell
            changes.append((i, agent, phone_raw, '', 'CLEAR'))
        elif cleaned == phone_raw:
            # Already clean — skip
            pass
        else:
            # Normalized
            changes.append((i, agent, phone_raw, cleaned, 'NORMALIZE'))
    
    # Stats
    clear_count = sum(1 for c in changes if c[4] == 'CLEAR')
    norm_count = sum(1 for c in changes if c[4] == 'NORMALIZE')
    
    print(f'Total phone cells: {sum(1 for r in rows[1:] if len(r) > 7 and r[7].strip())}')
    print(f'  CLEAR  (no valid number): {clear_count}')
    print(f'  NORMALIZE (format fix):    {norm_count}')
    print(f'  OK (already clean):        {478 - clear_count - norm_count}')
    print()
    
    if dry_run:
        print('=== DRY RUN — 预览前 30 条变更 ===')
        for r, ag, old, new, action in changes[:30]:
            if action == 'CLEAR':
                print(f'  行{r}: [{ag}] "{old[:50]}" → [删除]')
            else:
                print(f'  行{r}: [{ag}] "{old[:50]}" → "{new}"')
        
        if len(changes) > 30:
            print(f'  ... 还有 {len(changes)-30} 条')
        print()
        print('确认无误后执行: python3 scripts/clean_phones.py --apply')
    else:
        # Apply changes via batchUpdate
        if not changes:
            print('无需变更。')
            return
        
        # Build requests
        requests = []
        for r_num, ag, old, new, action in changes:
            requests.append({
                'updateCells': {
                    'range': {
                        'sheetId': 0,
                        'startRowIndex': r_num - 1,
                        'endRowIndex': r_num,
                        'startColumnIndex': 7,  # H
                        'endColumnIndex': 8
                    },
                    'rows': [{'values': [{'userEnteredValue': {'stringValue': new}}]}],
                    'fields': 'userEnteredValue'
                }
            })
        
        # Send in batches of 50
        for batch_start in range(0, len(requests), 50):
            batch = requests[batch_start:batch_start + 50]
            svc.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={'requests': batch}
            ).execute()
            print(f'  已写入 {batch_start + len(batch)}/{len(requests)}')
        
        print(f'\n✅ 完成！{clear_count} 格清空，{norm_count} 格标准化。')


if __name__ == '__main__':
    main()
