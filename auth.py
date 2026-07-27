import os
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from config import SCOPES, SERVICE_ACCOUNT_FILE

def authenticate_google():
    if os.path.exists(SERVICE_ACCOUNT_FILE):
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
    elif "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        
    else:
        raise FileNotFoundError(
            "Google Service Account credentials not found. "
            "Provide 'service_account.json' locally or configure 'gcp_service_account' in Streamlit secrets."
        )

    gc = gspread.authorize(creds)
    return creds, gc