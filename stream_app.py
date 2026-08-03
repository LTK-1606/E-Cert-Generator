import streamlit as st
import fitz
from auth import authenticate_google
from processor import run_generation
from cert_generator import generate_cert

st.set_page_config(
    page_title="E-Cert Generator",
    page_icon="📜",
    layout="wide"
)

st.title("📜 E-Cert Generator")

st.header("Step 1: Upload PDF Template")
uploaded_template = st.file_uploader("Upload your template (Ensure the areas to be filled in are blank)", type=["pdf"])

st.divider()

st.header("Step 2: Connect Google Sheet and Target Google Shared Drive")
sheet_url = st.text_input("Google Sheet URL", placeholder="https://docs.google.com/spreadsheets/d/...", help="Paste the URL of the Google Sheet containing the data for certificate generation. Ensure the Service Account email has access to this sheet.")

drive_folder_url = st.text_input(
    "Google Drive Folder Link (Optional)", 
    placeholder="https://drive.google.com/drive/folders/...",
    help="Paste a shared Google Drive folder link where certificates should be uploaded. Leave blank to use default folder. Ensure the Service Account email has access to this drive."
)

if st.button("Load Worksheets"):
    if not sheet_url:
        st.warning("Please enter a Google Sheet URL.")
    else:
        with st.spinner("Authenticating and fetching worksheets..."):
            try:
                _, gc = authenticate_google()
                sh = gc.open_by_url(sheet_url)
                
                worksheets = [ws.title for ws in sh.worksheets()]
                st.session_state["worksheets"] = worksheets
                st.session_state["loaded_url"] = sheet_url
                st.success("Worksheets loaded successfully! Select your sheets below.")
                
            except Exception as e:
                st.error(f"Failed to access Google Sheet.\n\nError: {e}")

st.divider()

selected_sheets = []
primary_col = None
user_id_col = None
template_config = {}

if "worksheets" in st.session_state and uploaded_template:
    st.header("Step 3: Select Sheets & Columns to Map")
    
    st.write("**A. Choose Worksheets:**")
    selected_sheets = st.multiselect(
        "Ensure every worksheeet you select has the same column structure. The first row of each sheet should contain headers.",
        options=st.session_state["worksheets"],
        key="selected_sheets_multiselect"
    )
    
    if selected_sheets:
        try:
            _, gc = authenticate_google()
            sh = gc.open_by_url(st.session_state["loaded_url"])
            ws = sh.worksheet(selected_sheets[0])
            headers = ws.row_values(1)

            if 'School Term' not in headers:
                headers.append('School Term')

            sample_data = {}
            if ws.row_count > 1:
                row2 = ws.row_values(2)
                sample_data = dict(zip(headers, row2 + [''] * (len(headers) - len(row2))))
            
            st.session_state["sheet_headers"] = headers
            st.session_state["sample_row"] = sample_data
            
        except Exception as e:
            st.error(f"Failed to fetch headers for sheet '{selected_sheets[0]}': {e}")
            headers = []

        if headers:
            st.divider()
            st.write("**B. Certificate Term Details:**")
            school_term = st.text_input(
                "School Term", 
                value="Academic Year 2026 Term 2.", 
                key="school_term_input",
                help="This value will be dynamically included in all rows."
            )
            
            st.divider()
            st.write("**C. Select Key Columns:**")
            col_a, col_b = st.columns(2)
            with col_a:
                primary_col = st.selectbox(
                    "Which column should be used for the cert's name?",
                    options=headers,
                    key="primary_col_select"
                )
            with col_b:
                user_id_col = st.selectbox(
                    "Which column should be used for the unique User ID for file naming?",
                    options=headers,
                    key="user_id_col_select"
                )
                
            st.divider()
            
            st.write("**D. Map Column Coordinates & Fonts:**")
            selected_cols = st.multiselect(
                "Select the columns from your sheet you want to include (Ensure every sheet selected contains all the columns you select below)",
                options=headers,
                default=headers[:3] if len(headers) >= 3 else headers
            )
            
            col_settings, col_preview = st.columns([1, 1.2])
            
            with col_settings:
                st.info("Adjust the X (horizontal) and Y (vertical) positions. (0,0 is the bottom-left corner of the page).")
                for i, col in enumerate(selected_cols):
                    sample_val = school_term if col == 'School Term' else st.session_state['sample_row'].get(col, '')
                    st.markdown(f"**Field: `{col}`** *(Sample: {st.session_state['sample_row'].get(col, '')})*")
                    c1, c2, c3 = st.columns(3)
                    x = c1.number_input("X Position", value=300, key=f"x_{col}", step=10)
                    y = c2.number_input("Y Position", value=470 - (i*50), key=f"y_{col}", step=10)
                    size = c3.number_input("Font Size", value=20, key=f"size_{col}", step=2)
                    center = st.checkbox("Center align", value=True, key=f"center_{col}")
                    
                    template_config[col] = {"x": x, "y": y, "font_size": size, "center_align": center, "max_width": 450}
                    
            with col_preview:
                st.markdown("**Live PDF Preview**")
                if st.button("🔄 Generate Preview", type="secondary", use_container_width=True):
                    template_bytes = uploaded_template.getvalue()
                    
                    sample_row = dict(st.session_state["sample_row"])
                    sample_row['School Term'] = school_term
                    if 'Level' in sample_row:
                        val_str = str(sample_row['Level']).strip()
                        if val_str and val_str.lower() != 'nan' and not val_str.lower().startswith('primary'):
                            sample_row['Level'] = f"Primary {val_str}"
                    
                    preview_bytes = generate_cert(template_bytes, sample_row, template_config)
                    
                    doc = fitz.open(stream=preview_bytes, filetype="pdf")
                    for page_num in range(len(doc)):
                        page = doc[page_num]
                        pix = page.get_pixmap()
                        img_bytes = pix.tobytes("png")
                        st.image(img_bytes, use_container_width=True)

else:
    st.info("Please upload a PDF template and load your Google Sheet worksheets above to continue.")

st.divider()

if st.button("🚀 Start Bulk Generation & Upload", type="primary", use_container_width=True):
    if not uploaded_template:
        st.error("Please upload a PDF template.")
    elif not sheet_url:
        st.error("Please enter a Google Sheet URL.")
    elif not selected_sheets:
        st.error("Please select at least one sheet to process.")
    elif not primary_col:
        st.error("Please select a name column.")
    elif not user_id_col:
        st.error("Please select a user ID column.")
    elif not template_config:
        st.error("Please map at least one field for the certificate template.")
    else:
        with st.status("Processing Certificates...", expanded=True) as status:
            sheet_status = st.empty()
            col1, col2 = st.columns(2)

            with col1:
                st.write("**PDF Generation**")
                gen_label = st.empty()
                gen_bar = st.progress(0)

            with col2:
                st.write("**Drive Uploads**")
                upload_label = st.empty()
                upload_bar = st.progress(0)

            def update_sheet_label(name):
                sheet_status.write(f"📁 **Currently Processing Sheet:** `{name}`")

            def update_gen_progress(current, total):
                progress_ratio = current / total if total > 0 else 0.0
                gen_bar.progress(progress_ratio)
                gen_label.caption(f"PDF Generation Progress: **{current} / {total}**")

            def update_upload_progress(current, total):
                progress_ratio = current / total if total > 0 else 0.0
                upload_bar.progress(progress_ratio)
                upload_label.caption(f"Drive Upload Progress: **{current} / {total}**")

            try:
                template_bytes = uploaded_template.getvalue()
                run_generation(
                    sheet_url=sheet_url,
                    target_sheets=selected_sheets,
                    primary_col=primary_col,
                    user_id_col=user_id_col,
                    template_config=template_config,
                    template_bytes=template_bytes,
                    school_term=st.session_state.get("school_term_input", "Academic Year 2026 Term 2"),
                    target_drive_folder=drive_folder_url,
                    sheet_callback=update_sheet_label,
                    gen_callback=update_gen_progress,
                    upload_callback=update_upload_progress
                )
                
                status.update(label="All tasks finished successfully!", state="complete", expanded=False)
                st.session_state["process_completed"] = True

            except Exception as e:
                status.update(label="An error occurred during processing.", state="error", expanded=True)
                st.error(f"Processing failed: {e}")

if st.session_state.get("process_completed", False):
    st.balloons()
    st.success("✨ Certificates generated, uploaded, and sheet updated successfully!")
    del st.session_state["process_completed"]