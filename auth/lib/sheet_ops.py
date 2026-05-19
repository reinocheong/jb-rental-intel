from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SA_KEY = '/home/user/.hermes/google_sa_rental.json'

def get_sheets_svc():
    creds = Credentials.from_service_account_file(SA_KEY, scopes=['https://www.googleapis.com/auth/spreadsheets'])
    return build('sheets', 'v4', credentials=creds)

def read_sheet(sheet_id, range_str):
    svc = get_sheets_svc()
    result = svc.spreadsheets().values().get(spreadsheetId=sheet_id, range=range_str).execute()
    return result.get('values', [])

def append_row(sheet_id, range_str, values):
    svc = get_sheets_svc()
    svc.spreadsheets().values().append(spreadsheetId=sheet_id, range=range_str, valueInputOption='USER_ENTERED', body={'values': [values]}).execute()
