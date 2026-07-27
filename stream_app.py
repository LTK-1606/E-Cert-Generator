import streamlit as st
from auth import authenticate_google
from processor import run_generation

st.set_page_config(
    page_title="Google Sheets E-Cert Automation",
    page_icon="📜",
    layout="wide"
)

st.title("📜 Google Sheets E-Cert Automation")

st.header("Step 1: Paste Google Sheet URL")
sheet_url = st.text_input("Google Sheet URL", placeholder="https://docs.google.com/spreadsheets/d/...", label_visibility="collapsed")

if st.button("Load Sheets"):
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
                st.success("Sheets loaded successfully!")
            except Exception as e:
                st.error(f"Failed to access Google Sheet.\n\nError: {e}")

st.divider()

st.header("Step 2: Select Sheets to Process")
selected_sheets = []

if "worksheets" in st.session_state:
    st.write("Choose the worksheets you want to generate certs for:")
    for sheet_name in st.session_state["worksheets"]:
        if st.checkbox(sheet_name, key=f"chk_{sheet_name}"):
            selected_sheets.append(sheet_name)
else:
    st.info("Please load a Google Sheet URL above first.")

st.divider()

st.header("Step 3: Enter School Term")
school_term = st.text_input("School Term", value="Academic Year 2026 Term 2")

st.divider()

if st.button("Start Generation & Upload", type="primary", use_container_width=True):
    if not sheet_url:
        st.error("Please enter a Google Sheet URL.")
    elif not selected_sheets:
        st.error("Please select at least one sheet to process.")
    elif not school_term:
        st.error("Please enter a school term.")
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
                run_generation(
                    sheet_url,
                    selected_sheets,
                    school_term,
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