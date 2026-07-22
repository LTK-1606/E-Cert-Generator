import os
import gspread
from google.oauth2.service_account import Credentials
from config import SERVICE_ACCOUNT_FILE, SCOPES

def authenticate_google():
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Missing {SERVICE_ACCOUNT_FILE}. Please place it in the script directory.")
        
    creds = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
    gc = gspread.authorize(creds)
    return creds, gc