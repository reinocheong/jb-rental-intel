from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime

SA_KEY_FILE = "/home/user/.hermes/google_sa_key.json"
SHEET_ID = "1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM"

def get_drive_service():
    creds = Credentials.from_service_account_file(SA_KEY_FILE, scopes=["https://www.googleapis.com/auth/drive"])
    return build("drive", "v3", credentials=creds)

def get_sheets_service():
    creds = Credentials.from_service_account_file(SA_KEY_FILE, scopes=["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"])
    return build("sheets", "v4", credentials=creds), build("drive", "v3", credentials=creds)

def get_forms_service():
    creds = Credentials.from_service_account_file(SA_KEY_FILE, scopes=["https://www.googleapis.com/auth/forms.responses.readonly", "https://www.googleapis.com/auth/forms.body"])
    return build("forms", "v1", credentials=creds)

def share_sheet(email):
    print(f"[sub_mgr/google_ops.py][google] 分享 Sheet 给 {email}")
    drive = get_drive_service()
    permission = {"type": "user", "role": "reader", "emailAddress": email}
    try:
        result = drive.permissions().create(fileId=SHEET_ID, body=permission, sendNotificationEmail=True,
            emailMessage=f"🎉 感谢订阅 JB Rental Intel！\n\n你的数据表已开通：\nhttps://docs.google.com/spreadsheets/d/{SHEET_ID}/edit").execute()
        return result.get("id")
    except Exception as e:
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr/google_ops.py] [L22] [Share] -> {e}\n")
        return None

def revoke_sheet(email):
    print(f"[sub_mgr/google_ops.py][google] 回收 {email} 权限")
    drive = get_drive_service()
    try:
        perms = drive.permissions().list(fileId=SHEET_ID, fields="permissions(id,emailAddress)").execute()
        for p in perms.get("permissions", []):
            if p.get("emailAddress", "").lower() == email.lower() and p.get("role") != "owner":
                drive.permissions().delete(fileId=SHEET_ID, permissionId=p["id"]).execute()
                return p["id"]
    except Exception as e:
        with open("/home/user/jb-rental-intel/.logs/error.log", "a") as f:
            f.write(f"[{datetime.now().isoformat()}] [sub_mgr/google_ops.py] [L35] [Revoke] -> {e}\n")
    return None

def check_shared(email):
    drive = get_drive_service()
    try:
        perms = drive.permissions().list(fileId=SHEET_ID, fields="permissions(id,emailAddress,role)").execute()
        for p in perms.get("permissions", []):
            if p.get("emailAddress", "").lower() == email.lower(): return p.get("role")
    except: pass
    return None
