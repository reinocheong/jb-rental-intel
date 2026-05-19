"""Google Sheets writer utilities."""
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

def get_sheets_service(sa_key_file):
    """Authenticate and return Google Sheets service."""
    creds = Credentials.from_service_account_file(sa_key_file,
        scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return build("sheets", "v4", credentials=creds)

def read_sheet(service, sheet_id, range_name):
    """Read values from a sheet."""
    result = service.spreadsheets().values().get(
        spreadsheetId=sheet_id, range=range_name).execute()
    return result.get("values", [])

def append_rows(service, sheet_id, range_name, values):
    """Append rows to a sheet."""
    return service.spreadsheets().values().append(
        spreadsheetId=sheet_id,
        range=range_name,
        body={"values": values},
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS"
    ).execute()

def update_range(service, sheet_id, range_name, values):
    """Update a specific range."""
    return service.spreadsheets().values().update(
        spreadsheetId=sheet_id,
        range=range_name,
        body={"values": values},
        valueInputOption="RAW"
    ).execute()
