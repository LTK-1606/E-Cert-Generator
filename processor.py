import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from tenacity import RetryError

from config import DRIVE_FOLDER_ID, TEMP_DIR
from auth import authenticate_google
from drive_utils import col_to_letter, get_or_create_subfolder, get_existing_files_in_folder, upload_file
from cert_generator import generate_cert

def run_generation(sheet_url, target_sheets, school_term, sheet_callback=None, gen_callback=None, upload_callback=None):
    if not target_sheets:
        messagebox.showerror("Error", "Please select at least one sheet.")
        return
    if not school_term:
        messagebox.showerror("Error", "Please enter a school term.")
        return

    try:
        creds, gc = authenticate_google()
        drive_service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        messagebox.showerror("Authentication Error", str(e))
        return
    
    try:
        sh = gc.open_by_url(sheet_url)
        identifier = sh.title.split(' ')[0]
    except Exception as e:
        messagebox.showerror("Error", f"Could not open Google Sheet. Did you share it with the Service Account email?\n{e}")
        return

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

        sheet_folder_id = get_or_create_subfolder(drive_service, DRIVE_FOLDER_ID, sheet_name, identifier)  
        existing_files = get_existing_files_in_folder(drive_service, sheet_folder_id)     

        valid_rows = []
        for index, row in df.iterrows():
            if 'Full Name' in df.columns and str(row.get('Full Name', '')).strip() != "":
                name = str(row.get('Full Name', '')).strip()
            elif 'Child Name' in df.columns and str(row.get('Child Name', '')).strip() != "":
                name = str(row.get('Child Name', '')).strip()
            else:
                name = ""
            
            if name:
                valid_rows.append((index, row, name))

        total_valid = len(valid_rows)
        if gen_callback:
            gen_callback(0, total_valid)
        if upload_callback:
            upload_callback(0, total_valid)

        upload_tasks = []
        skipped_count = 0
        gen_count = 0
        with ThreadPoolExecutor(max_workers=20) as executor:
            for index, row, name in valid_rows:
                id = row.get('User ID', '')
                level = row.get('Level', '')
                school = row.get('School', '')
                
                safe_name = name.replace('/', '-').replace('\\', '-')
                safe_id = str(id).replace('/', '-').replace('\\', '-')
                
                file_name = f"{identifier}-{safe_name}-{safe_id}.pdf"

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
                generate_cert(name, level, school, school_term, local_path)
                
                gen_count += 1
                if gen_callback:
                    gen_callback(gen_count, total_valid)
                
                future = executor.submit(upload_file, creds, sheet_folder_id, local_path, file_name)
                upload_tasks.append((index, local_path, future))

            upload_count = skipped_count
            for index, path, future in upload_tasks:
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

                finally:
                    if os.path.exists(path):
                        os.remove(path)

                    upload_count += 1
                    if upload_callback:
                        upload_callback(upload_count, total_valid)

        try:
            header = worksheet.row_values(1)

            def get_or_add_column(col_name, current_header):
                if col_name not in current_header:
                    new_idx = len(current_header) + 1
                    worksheet.update_cell(1, new_idx, col_name)
                    current_header.append(col_name)
                    return new_idx
                return current_header.index(col_name) + 1
            
            link_col_idx = get_or_add_column('Cert_Link', header)
            id_col_idx = get_or_add_column('Cert_Link_ID', header)

            link_col_letter = col_to_letter(link_col_idx)
            link_range = f"{link_col_letter}2:{link_col_letter}{len(df) + 1}"
            links_to_upload = [[str(df.at[i, 'Cert_Link'])] for i in df.index]
            worksheet.update(values=links_to_upload, range_name=link_range)

            id_col_letter = col_to_letter(id_col_idx)
            id_range = f"{id_col_letter}2:{id_col_letter}{len(df) + 1}"
            ids_to_upload = [[str(df.at[i, 'Cert_Link_ID'])] for i in df.index]
            worksheet.update(values=ids_to_upload, range_name=id_range)
            
        except Exception as e:
            messagebox.showerror("Sheets Update Error", f"Failed to write to Google Sheet for {sheet_name}.\nError: {str(e)}")
            return 
        
    messagebox.showinfo("Success", "Certificates generated, uploaded, and sheet updated successfully!")