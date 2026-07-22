from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from tenacity import retry, wait_exponential, stop_after_attempt
from config import _FOLDER_CACHE

def col_to_letter(col_idx):
    string = ""
    while col_idx > 0:
        col_idx, remainder = divmod(col_idx - 1, 26)
        string = chr(65 + remainder) + string
    return string

def get_or_create_subfolder(drive_service, parent_folder_id, sheet_name, identifier):
    folder_name = identifier + "-" + sheet_name
    cache_key = (parent_folder_id, folder_name)
    if cache_key in _FOLDER_CACHE:
        return _FOLDER_CACHE[cache_key]
    
    escaped_name = folder_name.replace("'", "\\'")
    query = (
        f"'{parent_folder_id}' in parents and "
        f"name = '{escaped_name}' and "
        f"mimeType = 'application/vnd.google-apps.folder' and "
        f"trashed = false"
    )
    
    response = drive_service.files().list(
        q=query, spaces='drive', fields='files(id, name)', supportsAllDrives=True, includeItemsFromAllDrives=True
    ).execute()
    
    files = response.get('files', [])
    if files:
        folder_id = files[0]['id']
    else:
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }
        folder = drive_service.files().create(
            body=folder_metadata, 
            fields='id', 
            supportsAllDrives=True
        ).execute()
        folder_id = folder.get('id')

    _FOLDER_CACHE[cache_key] = folder_id
    return folder_id

def get_existing_files_in_folder(drive_service, folder_id):
    existing_files = {}
    page_token = None
    query = f"'{folder_id}' in parents and trashed = false"

    while True:
        response = drive_service.files().list(
            q=query,
            spaces='drive',
            fields='nextPageToken, files(id, name, webViewLink)',
            supportsAllDrives=True,
            includeItemsFromAllDrives=True,
            pageToken=page_token
        ).execute()

        for file in response.get('files', []):
            existing_files[file['name']] = {
                'id': file['id'],
                'link': file.get('webViewLink', '')
            }

        page_token = response.get('nextPageToken', None)
        if page_token is None:
            break

    return existing_files

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(5))
def upload_file(creds, target_folder_id, file_path, file_name):
    drive_service = build('drive', 'v3', credentials=creds)

    file_metadata = {'name': file_name, 'parents': [target_folder_id]}
    with open(file_path, 'rb') as f:
        media = MediaIoBaseUpload(f, mimetype='application/pdf', resumable=True)
        
        uploaded_file = drive_service.files().create(
            body=file_metadata, media_body=media, fields='id, webViewLink', supportsAllDrives=True
        ).execute()
        
    return uploaded_file.get('webViewLink'), uploaded_file.get('id')