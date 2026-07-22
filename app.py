import threading
import tkinter as tk
from tkinter import messagebox, ttk

from auth import authenticate_google
from processor import run_generation

class CertApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Google Sheets E-Cert Automation")
        self.root.geometry("540x800")
        
        self.sheet_vars = {}
        self.gc = None
        self.current_sh = None
        
        tk.Label(root, text="Step 1: Paste Google Sheet URL", font=("Helvetica", 11, "bold")).pack(pady=(15, 5))
        self.entry_url = tk.Entry(root, width=55)
        self.entry_url.pack(pady=5)
        
        self.btn_load = tk.Button(root, text="Load Sheets", command=self.load_sheets)
        self.btn_load.pack()
        
        tk.Label(root, text="Step 2: Select Sheets to Process", font=("Helvetica", 11, "bold")).pack(pady=(15, 5))
        self.frame_checkboxes = tk.Frame(root)
        self.frame_checkboxes.pack()
        
        tk.Label(root, text="Step 3: Enter School Term", font=("Helvetica", 11, "bold")).pack(pady=(15, 5))
        self.entry_term = tk.Entry(root, width=45)
        self.entry_term.insert(0, "Academic Year 2026 Term 2")
        self.entry_term.pack()
        
        self.btn_run = tk.Button(root, text="Start Generation & Upload", bg="#4CAF50", fg="white", font=("Helvetica", 11, "bold"), command=self.start_process)
        self.btn_run.pack(pady=15)

        self.lbl_sheet_status = tk.Label(root, text="Currently Processing: None", font=("Helvetica", 10, "bold"), fg="#333333")
        self.lbl_sheet_status.pack(pady=(10, 5))

        self.lbl_gen_status = tk.Label(root, text="PDF Generation: 0 / 0", font=("Helvetica", 9), fg="gray")
        self.lbl_gen_status.pack()
        self.progress_gen = ttk.Progressbar(root, orient="horizontal", length=420, mode="determinate")
        self.progress_gen.pack(pady=(2, 10))

        self.lbl_upload_status = tk.Label(root, text="Drive Uploads: 0 / 0", font=("Helvetica", 9), fg="gray")
        self.lbl_upload_status.pack()
        self.progress_upload = ttk.Progressbar(root, orient="horizontal", length=420, mode="determinate")
        self.progress_upload.pack(pady=(2, 15))

    def load_sheets(self):
        url = self.entry_url.get().strip()
        if not url:
            messagebox.showwarning("Warning", "Please enter a Google Sheet URL.")
            return
            
        try:
            _, self.gc = authenticate_google()
            self.current_sh = self.gc.open_by_url(url)
            
            for widget in self.frame_checkboxes.winfo_children():
                widget.destroy()
            self.sheet_vars.clear()
            
            for worksheet in self.current_sh.worksheets():
                sheet_name = worksheet.title
                var = tk.BooleanVar(value=False)
                chk = tk.Checkbutton(self.frame_checkboxes, text=sheet_name, variable=var)
                chk.pack(anchor='w')
                self.sheet_vars[sheet_name] = var
                
            self.lbl_sheet_status.config(text="Status: Sheets loaded successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to access Google Sheet.\nError: {e}")

    def update_sheet_label(self, sheet_name):
        self.lbl_sheet_status.config(text=f"Currently Processing: {sheet_name}", fg="blue")
        self.root.update_idletasks()

    def update_gen_progress(self, current, total):
        self.progress_gen['maximum'] = total
        self.progress_gen['value'] = current
        self.lbl_gen_status.config(text=f"PDF Generation: {current} / {total}", fg="black")
        self.root.update_idletasks()

    def update_upload_progress(self, current, total):
        self.progress_upload['maximum'] = total
        self.progress_upload['value'] = current
        self.lbl_upload_status.config(text=f"Drive Uploads: {current} / {total}", fg="black")
        self.root.update_idletasks()

    def start_process(self):
        selected_sheets = [sheet for sheet, var in self.sheet_vars.items() if var.get()]
        term = self.entry_term.get().strip()
        url = self.entry_url.get().strip()
        
        if not url:
            messagebox.showwarning("Warning", "Please enter a Google Sheet URL.")
            return

        if not selected_sheets:
            messagebox.showwarning("Warning", "Please select at least one sheet.")
            return

        self.btn_run.config(state="disabled")
        def worker():
            run_generation(
                url, 
                selected_sheets, 
                term, 
                sheet_callback=self.update_sheet_label,
                gen_callback=self.update_gen_progress,
                upload_callback=self.update_upload_progress
            )
            self.root.after(0, lambda: self.btn_run.config(state="normal"))

        threading.Thread(target=worker, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    app = CertApp(root)
    root.mainloop()