from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

SA_KEY_FILE = "/home/user/.hermes/google_sa_key.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"

def get_sheets_service():
    creds = Credentials.from_service_account_file(SA_KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds)

def get_agents_from_sheet():
    svc = get_sheets_service()
    res = svc.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="JB Rentals!A:L").execute()
    values = res.get("values", [])
    if not values: return []
    headers = [h.lower() for h in values[0]]
    agents = []
    for row in values[1:]:
        d = dict(zip(headers, row + ['']*(len(headers)-len(row))))
        if d.get('phone'): agents.append({'agent': d.get('agent name'), 'phone': d.get('phone'), 'property': d.get('property name')})
    return agents
