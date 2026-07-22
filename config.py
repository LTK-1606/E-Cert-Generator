import os

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]
SERVICE_ACCOUNT_FILE = 'service_account.json'
TEMPLATE_PDF = "template.pdf"
DRIVE_FOLDER_ID = "163AlwTOgpzR28s5NrKK5tsmU5hzADaVb" 
TEMP_DIR = "temp_certs"

os.makedirs(TEMP_DIR, exist_ok=True)
_FOLDER_CACHE = {}