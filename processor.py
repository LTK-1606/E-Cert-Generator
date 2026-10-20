import os
import re
import streamlit as st
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from gspread.utils import rowcol_to_a1
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import RetryError

from config import DRIVE_FOLDER_ID, TEMP_DIR
from auth import authenticate_google
from drive_utils import col_to_letter, get_or_create_subfolder, get_existing_files_in_folder, upload_file
from cert_generator import generate_cert

def extract_folder_id(url_or_id):
    if not url_or_id:
        return None
    url_or_id = url_or_id.strip()
    match = re.search(r'folders/([a-zA-Z0-9-_]+)', url_or_id)
    if match:
        return match.group(1)
    return url_or_id

def run_generation(sheet_url, target_sheets, primary_col, user_id_col, template_config, template_bytes, school_term="", target_drive_folder="", sheet_callback=None, gen_callback=None, upload_callback=None):
    if not target_sheets:
        raise ValueError("Please select at least one sheet.")
    
    if not primary_col:
        raise ValueError("Please select a primary column for file naming and validation.")
        
    if not user_id_col:
        raise ValueError("Please select a user ID column for unique file naming.")

    try:
        creds, gc = authenticate_google()
        drive_service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        raise Exception(f"Authentication Error: {str(e)}")
    
    try:
        sh = gc.open_by_url(sheet_url)
        identifier = sh.title.split(' ')[0]
    except Exception as e:
        raise Exception(f"Could not open Google Sheet. Did you share it with the Service Account email?\n{e}")

    parent_folder_id = extract_folder_id(target_drive_folder) if target_drive_folder else DRIVE_FOLDER_ID
    if not parent_folder_id:
        parent_folder_id = DRIVE_FOLDER_ID

    for sheet_name in target_sheets:
        if sheet_callback:
            sheet_callback(sheet_name)
            
        worksheet = sh.worksheet(sheet_name)
        all_values = worksheet.get_all_values()

        if not all_values or len(all_values) <= 1:
            print(f"Sheet {sheet_name} is empty or has no data rows. Skipping.")
            continue

        raw_header = all_values[0]
        data_rows = all_values[1:]

        clean_header = [
            col if col.strip() != "" else f"Unnamed_{i}" 
            for i, col in enumerate(raw_header)
        ]

        df = pd.DataFrame(data_rows, columns=clean_header)        
        if 'Cert_Link' not in df.columns:
            df['Cert_Link'] = ""
        if 'Cert_Link_ID' not in df.columns:
            df['Cert_Link_ID'] = ""

        df['School Term'] = school_term

        if 'Level' in df.columns:
            def format_level(val):
                val_str = str(val).strip()
                if val_str and val_str.lower() != 'nan' and not val_str.lower().startswith('primary'):
                    return f"Primary {val_str}"
                return val_str
            df['Level'] = df['Level'].apply(format_level)

        sheet_folder_id = get_or_create_subfolder(drive_service, parent_folder_id, sheet_name, identifier)  
        existing_files = get_existing_files_in_folder(drive_service, sheet_folder_id)     

        valid_rows = []
        for index, row in df.iterrows():
            primary_val = ""
            if primary_col in df.columns and str(row.get(primary_col, '')).strip() != "":
                primary_val = str(row.get(primary_col, '')).strip()
            
            if primary_val:
                valid_rows.append((index, row, primary_val))

        total_valid = len(valid_rows)
        if gen_callback:
            gen_callback(0, total_valid)
        if upload_callback:
            upload_callback(0, total_valid)

        futures_map = {}
        skipped_count = 0
        gen_count = 0
        
        with ThreadPoolExecutor(max_workers=20) as executor:
            for index, row, primary_val in valid_rows:
                
                safe_primary_val = primary_val.replace('/', '-').replace('\\', '-')
                
                user_id_val = str(row.get(user_id_col, '')).strip() if user_id_col in df.columns else ""
                safe_user_id = user_id_val.replace('/', '-').replace('\\', '-') if user_id_val else f"Row{index+2}"
                
                file_name = f"{identifier}-{safe_primary_val}-{safe_user_id}.pdf"

                if file_name in existing_files:
                    df.at[index, 'Cert_Link'] = existing_files[file_name]['link']
                    df.at[index, 'Cert_Link_ID'] = existing_files[file_name]['id']
                    
                    skipped_count += 1
                    gen_count += 1
                    
                    if gen_callback:
                        gen_callback(gen_count, total_valid)
                    if upload_callback:
                        upload_callback(skipped_count, total_valid)
                    continue

                local_path = os.path.join(TEMP_DIR, file_name)
                row_dict = row.to_dict()
                generate_cert(template_bytes, row_dict, template_config, local_path)
                
                gen_count += 1
                if gen_callback:
                    gen_callback(gen_count, total_valid)
                
                future = executor.submit(upload_file, creds, sheet_folder_id, local_path, file_name)
                futures_map[future] = (index, local_path)

            upload_count = skipped_count
            
            for future in as_completed(futures_map):
                index, path = futures_map[future]
                try:
                    link, link_id = future.result()
                    df.at[index, 'Cert_Link'] = link
                    df.at[index, 'Cert_Link_ID'] = link_id

                except Exception as e:
                    print(f"\n--- ERROR ON ROW {index} ---")
                    df.at[index, 'Cert_Link'] = "UPLOAD ERROR"
                    df.at[index, 'Cert_Link_ID'] = "UPLOAD ERROR"
                    
                    actual_error = e
                    if isinstance(e, RetryError):
                        actual_error = e.last_attempt.exception()

                    if isinstance(actual_error, HttpError):
                        print(f"HTTP Status Code: {actual_error.resp.status}")
                        print(f"Error Details: {actual_error.content.decode('utf-8')}")
                    else:
                        print(f"General Error: {actual_error}")

                    st.warning(f"Failed to upload row {index+2}: {actual_error}")

                finally:
                    if os.path.exists(path):
                        os.remove(path)

                    upload_count += 1
                    if upload_callback:
                        upload_callback(upload_count, total_valid)

        try:
            sheet_header_labels  = worksheet.row_values(1)

            def get_or_add_column(col_name, current_header):
                if col_name not in current_header:
                    new_idx = len(current_header) + 1
                    worksheet.update_cell(1, new_idx, col_name)
                    current_header.append(col_name)
                    return new_idx
                return current_header.index(col_name) + 1
            
            link_col_idx = get_or_add_column('Cert_Link', sheet_header_labels)
            id_col_idx = get_or_add_column('Cert_Link_ID', sheet_header_labels)

            batch_updates = []

            for index, row in df.iterrows():
                target_row = index + 2 
                
                batch_updates.append({
                    'range': rowcol_to_a1(target_row, link_col_idx),
                    'values': [[str(row.get('Cert_Link', ''))]]
                })
                
                batch_updates.append({
                    'range': rowcol_to_a1(target_row, id_col_idx),
                    'values': [[str(row.get('Cert_Link_ID', ''))]]
                })

            if batch_updates:
                worksheet.batch_update(batch_updates)
            
        except Exception as e:
            raise Exception(f"Failed to write to Google Sheet for {sheet_name}.\nError: {str(e)}")
            
    return True