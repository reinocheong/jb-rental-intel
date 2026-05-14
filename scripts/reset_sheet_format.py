"""
还原 JB Rentals Sheet — 清除所有格式，回到裸数据状态
"""
import sys
sys.path.insert(0, '/home/user/jb-rental-intel')
from processors.fb_parser import get_sheets_service

SHEET_ID = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM'
SHEET_ID_NUM = 0

svc = get_sheets_service()

requests = [
    # 解冻表头
    {"updateSheetProperties": {
        "properties": {"sheetId": SHEET_ID_NUM, "gridProperties": {"frozenRowCount": 0}},
        "fields": "gridProperties.frozenRowCount"
    }},
    # 清除所有交替颜色
    {"removeBanding": {"bandedRangeId": None}},  # removes all banding
    # 全局重置格式（所有行所有列）
    {"repeatCell": {
        "range": {"sheetId": SHEET_ID_NUM},
        "cell": {"userEnteredFormat": {}},
        "fields": "userEnteredFormat"
    }},
    # 全局边框去掉
    {"updateBorders": {
        "range": {"sheetId": SHEET_ID_NUM, "startColumnIndex": 0, "endColumnIndex": 12},
        "top": {"style": "NONE"}, "bottom": {"style": "NONE"},
        "left": {"style": "NONE"}, "right": {"style": "NONE"},
        "innerHorizontal": {"style": "NONE"}, "innerVertical": {"style": "NONE"}
    }},
    # 恢复默认列宽
    {"updateDimensionProperties": {
        "range": {"sheetId": SHEET_ID_NUM, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 12},
        "properties": {"pixelSize": 100},
        "fields": "pixelSize"
    }},
]

print("还原 Sheet 格式...")
body = {"requests": requests}
svc.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
print("✅ 已还原为裸数据状态")
