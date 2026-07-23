import os
import sys

if hasattr(sys, '_MEIPASS'):
    # PyInstaller compiled bundle
    exe_dir = os.path.dirname(sys.executable)
    
    if sys.platform == 'darwin' and '.app/Contents/MacOS' in exe_dir:
        # macOS Bundle (.app container)
        EXTERNAL_DIR = os.path.abspath(os.path.join(exe_dir, '../../..'))
    else:
        # Windows / Linux executable folder
        EXTERNAL_DIR = exe_dir
else:
    # Standard uncompiled Python script
    EXTERNAL_DIR = os.path.abspath(".")

def get_resource_path(relative_path, internal=True):
    """
    Get absolute path to resource.
    - internal=True : Fetches from PyInstaller's temporary _MEIPASS folder (bundled via --add-data).
    - internal=False: Fetches from EXTERNAL_DIR (the folder where the executable file actually lives).
    """
    if internal:
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, relative_path)
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)
    else:
        return os.path.join(EXTERNAL_DIR, relative_path)

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]
SERVICE_ACCOUNT_FILE = get_resource_path('service_account.json', internal=False)
TEMPLATE_PDF = get_resource_path("template.pdf", internal=True)
DRIVE_FOLDER_ID = "163AlwTOgpzR28s5NrKK5tsmU5hzADaVb" 
TEMP_DIR = "temp_certs"

os.makedirs(TEMP_DIR, exist_ok=True)
_FOLDER_CACHE = {}