"""
美化 JB Rentals Sheet — 纯格式操作，不修改任何数据
可撤销：Google Sheets 内 Ctrl+Z
可还原：运行 reset_sheet_format.py
"""
import sys
sys.path.insert(0, '/home/user/jb-rental-intel')
from processors.fb_parser import get_sheets_service

SHEET_ID = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM'
SHEET_NAME = 'JB Rentals'
SHEET_ID_NUM = 0  # first sheet

svc = get_sheets_service()

requests = []

# ── ① 冻结表头行 ──
requests.append({
    "updateSheetProperties": {
        "properties": {
            "sheetId": SHEET_ID_NUM,
            "gridProperties": {"frozenRowCount": 1}
        },
        "fields": "gridProperties.frozenRowCount"
    }
})

# ── ② 表头行格式（深蓝底白字粗体居中）──
requests.append({
    "repeatCell": {
        "range": {
            "sheetId": SHEET_ID_NUM,
            "startRowIndex": 0,
            "endRowIndex": 1
        },
        "cell": {
            "userEnteredFormat": {
                "backgroundColor": {"red": 0.06, "green": 0.13, "blue": 0.27},
                "textFormat": {
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                    "bold": True,
                    "fontSize": 10
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
        },
        "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment)"
    }
})

# ── ③ 斑马条纹（手写repeatCell，不用banding API避免headerColor bug）──
# 先设全局白底 + 黑字
requests.append({
    "repeatCell": {
        "range": {"sheetId": SHEET_ID_NUM, "startRowIndex": 1, "endRowIndex": 800},
        "cell": {"userEnteredFormat": {
            "backgroundColor": {"red": 1, "green": 1, "blue": 1},
            "textFormat": {"foregroundColor": {"red": 0, "green": 0, "blue": 0}}
        }},
        "fields": "userEnteredFormat(backgroundColor,textFormat)"
    }
})
# 奇数数据行（第2,4,6...行）浅蓝底
for row in range(1, 800):
    if row % 2 == 1:
        requests.append({
            "repeatCell": {
                "range": {"sheetId": SHEET_ID_NUM, "startRowIndex": row, "endRowIndex": row + 1},
                "cell": {"userEnteredFormat": {
                    "backgroundColor": {"red": 0.97, "green": 0.98, "blue": 0.99}
                }},
                "fields": "userEnteredFormat(backgroundColor)"
            }
        })

# ── ④ 条件格式：Listing Type ──
# 出租 → 浅绿底 (Column C, index 2)
requests.append({
    "addConditionalFormatRule": {
        "rule": {
            "ranges": [{
                "sheetId": SHEET_ID_NUM,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3
            }],
            "booleanRule": {
                "condition": {
                    "type": "TEXT_EQ",
                    "values": [{"userEnteredValue": "出租"}]
                },
                "format": {
                    "backgroundColor": {"red": 0.86, "green": 0.98, "blue": 0.86}
                }
            }
        }
    }
})

# 出售 → 浅蓝底
requests.append({
    "addConditionalFormatRule": {
        "rule": {
            "ranges": [{
                "sheetId": SHEET_ID_NUM,
                "startRowIndex": 1,
                "startColumnIndex": 2,
                "endColumnIndex": 3
            }],
            "booleanRule": {
                "condition": {
                    "type": "TEXT_EQ",
                    "values": [{"userEnteredValue": "出售"}]
                },
                "format": {
                    "backgroundColor": {"red": 0.86, "green": 0.93, "blue": 0.98}
                }
            }
        }
    }
})

# ── ⑤ 列宽 ──
col_widths = {
    0: 140,   # Agent Name
    1: 280,   # Property Name
    2: 60,    # Listing Type
    3: 100,   # Property Type
    4: 80,    # Rooms
    5: 100,   # Furnishing
    6: 90,    # Rent
    7: 130,   # Phone
    8: 60,    # Link
    9: 120,   # Remark
    10: 120,  # Scraped At
    11: 350,  # Post Text
}

for col, width in col_widths.items():
    requests.append({
        "updateDimensionProperties": {
            "range": {
                "sheetId": SHEET_ID_NUM,
                "dimension": "COLUMNS",
                "startIndex": col,
                "endIndex": col + 1
            },
            "properties": {"pixelSize": width},
            "fields": "pixelSize"
        }
    })

# ── ⑥ 特定列格式 ──
# Rent (col 6): 右对齐
requests.append({
    "repeatCell": {
        "range": {
            "sheetId": SHEET_ID_NUM,
            "startRowIndex": 1,
            "startColumnIndex": 6,
            "endColumnIndex": 7
        },
        "cell": {
            "userEnteredFormat": {
                "horizontalAlignment": "RIGHT"
            }
        },
        "fields": "userEnteredFormat(horizontalAlignment)"
    }
})

# Phone (col 7): 等宽字体
requests.append({
    "repeatCell": {
        "range": {
            "sheetId": SHEET_ID_NUM,
            "startRowIndex": 1,
            "startColumnIndex": 7,
            "endColumnIndex": 8
        },
        "cell": {
            "userEnteredFormat": {
                "textFormat": {
                    "fontFamily": "Roboto Mono"
                }
            }
        },
        "fields": "userEnteredFormat(textFormat)"
    }
})

# Link (col 8): 蓝色链接样式
requests.append({
    "repeatCell": {
        "range": {
            "sheetId": SHEET_ID_NUM,
            "startRowIndex": 1,
            "startColumnIndex": 8,
            "endColumnIndex": 9
        },
        "cell": {
            "userEnteredFormat": {
                "textFormat": {
                    "foregroundColor": {"red": 0.1, "green": 0.4, "blue": 0.8},
                    "underline": True
                }
            }
        },
        "fields": "userEnteredFormat(textFormat)"
    }
})

# Post Text (col 11): 换行 + 小字号
requests.append({
    "repeatCell": {
        "range": {
            "sheetId": SHEET_ID_NUM,
            "startRowIndex": 1,
            "startColumnIndex": 11,
            "endColumnIndex": 12
        },
        "cell": {
            "userEnteredFormat": {
                "wrapStrategy": "WRAP",
                "textFormat": {"fontSize": 8}
            }
        },
        "fields": "userEnteredFormat(wrapStrategy,textFormat)"
    }
})

# ── ⑦ 全局边框 ──
requests.append({
    "updateBorders": {
        "range": {
            "sheetId": SHEET_ID_NUM,
            "startRowIndex": 0,
            "startColumnIndex": 0,
            "endColumnIndex": 12
        },
        "top": {"style": "SOLID", "width": 1, "color": {"red": 0.85, "green": 0.85, "blue": 0.85}},
        "bottom": {"style": "SOLID", "width": 1, "color": {"red": 0.85, "green": 0.85, "blue": 0.85}},
        "left": {"style": "SOLID", "width": 1, "color": {"red": 0.85, "green": 0.85, "blue": 0.85}},
        "right": {"style": "SOLID", "width": 1, "color": {"red": 0.85, "green": 0.85, "blue": 0.85}},
        "innerHorizontal": {"style": "SOLID", "width": 1, "color": {"red": 0.92, "green": 0.92, "blue": 0.92}},
        "innerVertical": {"style": "SOLID", "width": 1, "color": {"red": 0.92, "green": 0.92, "blue": 0.92}}
    }
})

# ── Batch send ──
print(f"Sending {len(requests)} format requests...")

# Split into batches (API limit: 100 requests per call)
for i in range(0, len(requests), 50):
    batch = requests[i:i+50]
    body = {"requests": batch}
    svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    print(f"  Batch {i//50+1}: {len(batch)} requests ✓")

print("\n✅ Sheet 美化完成！")
print("   撤销：打开 Sheet 按 Ctrl+Z")
print("   还原：python3 scripts/reset_sheet_format.py")
