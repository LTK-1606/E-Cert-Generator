import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from config import SCOPES, SERVICE_ACCOUNT_FILE

def authenticate_google():
    if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
        
    gc = gspread.authorize(creds)
    return creds, gc