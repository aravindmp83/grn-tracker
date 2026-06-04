import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import tempfile
import json
from datetime import datetime

# ==========================================
# GOOGLE SHEETS & DRIVE AUTHENTICATION
# ==========================================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_google_credentials():
    creds_data = st.secrets["gcp_service_account"]
    if isinstance(creds_data, str):
        creds_data = json.loads(creds_data)
    return Credentials.from_service_account_info(creds_data, scopes=SCOPES)

def get_gspread_client():
    creds = get_google_credentials()
    return gspread.authorize(creds)

def get_spreadsheet():
    gc = get_gspread_client()
    return gc.open_by_key(st.secrets["spreadsheet_id"])

def get_drive_service():
    creds = get_google_credentials()
    return build('drive', 'v3', credentials=creds)

# ==========================================
# GOOGLE DRIVE FILE UPLOAD
# ==========================================

def upload_file_to_drive(local_file_path: str, filename: str) -> str:
    """
    Uploads a local file to Google Drive and returns the webViewLink.
    Requires 'drive_folder_id' in st.secrets.
    """
    try:
        drive_service = get_drive_service()
        folder_id = st.secrets.get("drive_folder_id")
        
        file_metadata = {
            'name': filename,
            'parents': [folder_id] if folder_id else []
        }
        
        media = MediaFileUpload(local_file_path, resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        return file.get('webViewLink')
    except Exception as e:
        print(f"Error uploading to Drive: {e}")
        return local_file_path # Fallback to local path if Drive fails

# ==========================================
# DATA ACCESS & CACHING
# ==========================================

def get_sheet_df(sheet_name: str) -> pd.DataFrame:
    """Reads a worksheet into a Pandas DataFrame."""
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="30")
        
    records = ws.get_all_records()
    if not records:
        # Define default columns if empty
        if sheet_name == "management_users":
            return pd.DataFrame(columns=["username", "password", "role", "name", "territory"])
        elif sheet_name == "vendor_users":
            return pd.DataFrame(columns=["vendor_code", "password", "password_changed"])
        elif sheet_name == "store_users":
            return pd.DataFrame(columns=["store_code", "password"])
        else:
            return pd.DataFrame()
            
    df = pd.DataFrame(records)
    # Ensure ID columns are string type to prevent pandas dropping leading zeros
    for col in df.columns:
        if "password" not in col.lower():
            df[col] = df[col].astype(str)
    return df

def update_sheet_df(sheet_name: str, df: pd.DataFrame):
    """Overwrites a worksheet with a Pandas DataFrame."""
    sh = get_spreadsheet()
    try:
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=sheet_name, rows="1000", cols="30")
        
    ws.clear()
    ws.update([df.columns.values.tolist()] + df.fillna("").values.tolist())

# ==========================================
# CORE DB API - AUTHENTICATION
# ==========================================

def authenticate_user(user_id: str, password_input: str):
    if not user_id or not password_input:
        return None
        
    clean_id = user_id.strip()
    clean_pwd = password_input.strip()
    
    # 1. Check management
    mgmt_df = get_sheet_df("management_users")
    if not mgmt_df.empty:
        mgmt_match = mgmt_df[mgmt_df['username'].str.lower() == clean_id.lower()]
        if not mgmt_match.empty:
            row = mgmt_match.iloc[0]
            if str(row['password']) == clean_pwd:
                return {
                    "role": "management",
                    "username": clean_id.lower(),
                    "management_role": row['role'],
                    "management_territory": row['territory'],
                    "name": row['name']
                }
            return {"error": "invalid_password"}
            
    # 2. Check vendor
    vend_df = get_sheet_df("vendor_users")
    if not vend_df.empty:
        vend_match = vend_df[vend_df['vendor_code'].str.upper() == clean_id.upper()]
        if not vend_match.empty:
            if str(vend_match.iloc[0]['password']) == clean_pwd:
                return {"role": "vendor", "vendor_code": clean_id.upper()}
            return {"error": "invalid_password"}
            
    # 3. Check store manager
    store_df = get_sheet_df("store_users")
    store_match = pd.DataFrame()
    if not store_df.empty and 'store_code' in store_df.columns:
        store_match = store_df[store_df['store_code'].str.upper() == clean_id.upper()]
        
    grn_df = get_sheet_df("grn_records")
    if not grn_df.empty and 'site' in grn_df.columns:
        store_exists = not grn_df[grn_df['site'].str.upper() == clean_id.upper()].empty
        
        if store_exists:
            if not store_match.empty:
                if str(store_match.iloc[0]['password']) == clean_pwd:
                    return {"role": "store_manager", "store_code": clean_id.upper()}
                return {"error": "invalid_password"}
            else:
                if clean_pwd.upper() == clean_id.upper():
                    return {"role": "store_manager", "store_code": clean_id.upper()}
                return {"error": "invalid_password"}
                
    return None

def update_management_password(username: str, new_password: str) -> bool:
    df = get_sheet_df("management_users")
    idx = df[df['username'].str.lower() == username.strip().lower()].index
    if not idx.empty:
        df.loc[idx, 'password'] = new_password
        update_sheet_df("management_users", df)
        return True
    return False

def update_vendor_password(vendor_code: str, new_password: str) -> bool:
    df = get_sheet_df("vendor_users")
    idx = df[df['vendor_code'].str.upper() == vendor_code.strip().upper()].index
    if not idx.empty:
        df.loc[idx, 'password'] = new_password
        df.loc[idx, 'password_changed'] = "1"
        update_sheet_df("vendor_users", df)
        return True
    return False

def update_store_password(store_code: str, new_password: str) -> bool:
    df = get_sheet_df("store_users")
    clean_store = store_code.strip().upper()
    
    idx = df[df['store_code'].str.upper() == clean_store].index
    if not idx.empty:
        df.loc[idx, 'password'] = new_password
    else:
        new_row = pd.DataFrame([{'store_code': clean_store, 'password': new_password}])
        df = pd.concat([df, new_row], ignore_index=True)
        
    update_sheet_df("store_users", df)
    return True

# ==========================================
# HELPER FOR GRN DATA (Types & Cleanup)
# ==========================================
def parse_grn_df(df: pd.DataFrame) -> list:
    """Cleans up the dataframe and returns a list of dictionaries like SQLite row factory."""
    if df.empty:
        return []
    
    # Cast specific columns back to numerics where expected by UI
    num_cols = ['id', 'quantity', 'grn_qty', 'pending_qty', 'days']
    for col in num_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
            
    float_cols = ['price', 'net_value', 'pending_value']
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0).astype(float)
            
    return df.to_dict('records')

def append_comment(current_log: str, sender: str, new_comment: str) -> str:
    if not new_comment or not new_comment.strip():
        return current_log
    new_entry = f"{sender}: {new_comment.strip()}"
    if current_log and str(current_log).strip():
        return f"{current_log}\\n{new_entry}"
    return new_entry

# ==========================================
# STORE DASHBOARD
# ==========================================

def get_pending_grns(store_code: str):
    df = get_sheet_df("grn_records")
    if df.empty: return []
    mask = (df['site'].str.upper() == store_code.strip().upper()) & (df['is_goods_received'].astype(str) == "0")
    return parse_grn_df(df[mask].sort_values(by="po_number"))

def get_completed_grns(store_code: str):
    df = get_sheet_df("grn_records")
    if df.empty: return []
    mask = (df['site'].str.upper() == store_code.strip().upper()) & (df['is_goods_received'].astype(str) == "1")
    return parse_grn_df(df[mask].sort_values(by="id", ascending=False))

def update_grn_record(po_number: str, site: str, grn_number: str, invoice_file_path: str, sender: str, store_comments: str = None) -> bool:
    df = get_sheet_df("grn_records")
    mask = (df['po_number'].astype(str) == str(po_number)) & (df['site'].str.upper() == site.upper())
    
    if not mask.any(): return False
    
    # Optional: Upload to drive if invoice provided
    drive_link = invoice_file_path
    if invoice_file_path and os.path.exists(invoice_file_path):
        drive_link = upload_file_to_drive(invoice_file_path, os.path.basename(invoice_file_path))
        
    df.loc[mask, 'is_goods_received'] = "1"
    df.loc[mask, 'is_invoice_received'] = "1"
    df.loc[mask, 'grn_number'] = str(grn_number)
    df.loc[mask, 'invoice_file_path'] = drive_link
    df.loc[mask, 'store_invoice_status'] = 'Received'
    df.loc[mask, 'goods_received_status'] = 'Yes'
    
    if store_comments and store_comments.strip():
        df.loc[mask, 'comments_log'] = df.loc[mask, 'comments_log'].apply(lambda log: append_comment(log, sender, store_comments))
        
    update_sheet_df("grn_records", df)
    return True

def update_store_invoice_status(po_number: str, site: str, invoice_status: str, sender: str, store_comments: str) -> bool:
    df = get_sheet_df("grn_records")
    mask = (df['po_number'].astype(str) == str(po_number)) & (df['site'].str.upper() == site.upper())
    
    if not mask.any(): return False
    
    df.loc[mask, 'store_invoice_status'] = invoice_status
    df.loc[mask, 'goods_received_status'] = 'Yes'
    
    if store_comments and store_comments.strip():
        df.loc[mask, 'comments_log'] = df.loc[mask, 'comments_log'].apply(lambda log: append_comment(log, sender, store_comments))
        
    update_sheet_df("grn_records", df)
    return True

def update_store_goods_received_issue(po_number: str, site: str, receipt_status: str, sender: str, store_comments: str) -> bool:
    df = get_sheet_df("grn_records")
    mask = (df['po_number'].astype(str) == str(po_number)) & (df['site'].str.upper() == site.upper())
    
    if not mask.any(): return False
    
    df.loc[mask, 'goods_received_status'] = receipt_status
    df.loc[mask, 'store_invoice_status'] = 'Not Received'
    df.loc[mask, 'is_goods_received'] = "0"
    
    if store_comments and store_comments.strip():
        prefixed = f"[{receipt_status}] {store_comments.strip()}"
        df.loc[mask, 'comments_log'] = df.loc[mask, 'comments_log'].apply(lambda log: append_comment(log, sender, prefixed))
        
    update_sheet_df("grn_records", df)
    return True

# ==========================================
# VENDOR DASHBOARD
# ==========================================

def get_vendor_records(vendor_code: str):
    df = get_sheet_df("grn_records")
    if df.empty: return []
    mask = (df['vendor'].str.upper() == vendor_code.strip().upper())
    return parse_grn_df(df[mask].sort_values(by="po_number"))

def update_vendor_invoice_and_comments(po_number: str, vendor: str, sender: str, vendor_invoice_path: str = None, new_comment: str = None) -> bool:
    df = get_sheet_df("grn_records")
    mask = (df['po_number'].astype(str) == str(po_number)) & (df['vendor'].str.upper() == vendor.upper())
    
    if not mask.any(): return False
    
    if vendor_invoice_path is not None:
        drive_link = vendor_invoice_path
        if os.path.exists(vendor_invoice_path):
            drive_link = upload_file_to_drive(vendor_invoice_path, os.path.basename(vendor_invoice_path))
        df.loc[mask, 'vendor_invoice_path'] = drive_link
        
    if new_comment and new_comment.strip():
        df.loc[mask, 'comments_log'] = df.loc[mask, 'comments_log'].apply(lambda log: append_comment(log, sender, new_comment))
        
    update_sheet_df("grn_records", df)
    return True

# ==========================================
# MANAGEMENT DASHBOARD
# ==========================================

def get_management_pending_records(role: str, territory: str):
    df = get_sheet_df("grn_records")
    if df.empty: return []
    
    # Filter for pending
    mask = (df['is_goods_received'].astype(str) == "0")
    
    if role == "cluster_manager":
        mask = mask & (df['cm'].str.upper() == territory.upper())
    elif role == "regional_manager":
        mask = mask & (df['rmm'].str.upper() == territory.upper())
    elif role == "mis_executive":
        pass # View all
    else:
        return []
        
    return parse_grn_df(df[mask].sort_values(by=["site", "po_number"]))

def sync_ho_pendency_data(df_up: pd.DataFrame) -> tuple:
    # 1. Clean column names
    cleaned_cols = []
    for col in df_up.columns:
        col_clean = str(col).strip().lower()
        col_clean = col_clean.replace(" ", "_").replace("/", "_").replace(".", "").replace("-", "_")
        col_clean = col_clean.replace("&", "and").replace("(", "").replace(")", "")
        cleaned_cols.append(col_clean)
    df_up.columns = cleaned_cols
    
    # Make datetimes string-safe
    for col in df_up.columns:
        if pd.api.types.is_datetime64_any_dtype(df_up[col]):
            df_up[col] = df_up[col].astype(str).replace("NaT", "").replace("nan", "")
            
    # Handle NaNs in object columns
    for col in df_up.select_dtypes(include=['object']):
        df_up[col] = df_up[col].fillna("")
        
    # Standard cleanups
    df_up['po_number'] = df_up['po_number'].astype(str).str.strip()
    df_up['vendor'] = df_up['vendor'].astype(str).str.strip()
    df_up['site'] = df_up['site'].astype(str).str.strip()
    df_up['item'] = df_up['item'].astype(str).str.strip()
    
    df_up['price'] = pd.to_numeric(df_up['price'], errors='coerce').fillna(0.0)
    df_up['quantity'] = pd.to_numeric(df_up['quantity'], errors='coerce').fillna(0).astype(int)
    df_up['grn_qty'] = pd.to_numeric(df_up['grn_qty'], errors='coerce').fillna(0).astype(int)
    df_up['pending_qty'] = pd.to_numeric(df_up['pending_qty'], errors='coerce').fillna(0).astype(int)
    df_up['net_value'] = pd.to_numeric(df_up['net_value'], errors='coerce').fillna(0.0)
    df_up['pending_value'] = pd.to_numeric(df_up['pending_value'], errors='coerce').fillna(0.0)
    df_up['days'] = pd.to_numeric(df_up['days'], errors='coerce').fillna(0).astype(int)
    
    # Sync with existing
    db_df = get_sheet_df("grn_records")
    
    if db_df.empty:
        # Initial push
        db_df = df_up.copy()
        db_df['is_goods_received'] = "0"
        db_df['is_invoice_received'] = "0"
        db_df['goods_received_status'] = 'Pending'
        db_df['store_invoice_status'] = 'Pending'
        db_df['id'] = range(1, len(db_df) + 1)
        update_sheet_df("grn_records", db_df)
        
        # Populate management_users initially
        sync_management_users_from_records(db_df)
        
        return (len(db_df), 0, 0)
        
    # Sync logic
    inserted_count = 0
    updated_count = 0
    auto_completed_count = 0
    
    # Combine keys for lookup
    db_df['__key__'] = db_df['po_number'].astype(str) + "_" + db_df['item'].astype(str)
    df_up['__key__'] = df_up['po_number'].astype(str) + "_" + df_up['item'].astype(str)
    
    uploaded_keys = set(df_up['__key__'])
    
    # Find records closed at HO
    mask_auto_close = (db_df['is_goods_received'].astype(str) == "0") & (~db_df['__key__'].isin(uploaded_keys))
    if mask_auto_close.any():
        auto_completed_count = mask_auto_close.sum()
        db_df.loc[mask_auto_close, 'is_goods_received'] = "1"
        db_df.loc[mask_auto_close, 'is_invoice_received'] = "1"
        db_df.loc[mask_auto_close, 'goods_received_status'] = "Yes"
        db_df.loc[mask_auto_close, 'store_invoice_status'] = "Received"
        db_df.loc[mask_auto_close, 'grn_number'] = "Closed at HO"
        db_df.loc[mask_auto_close, 'comments_log'] = db_df.loc[mask_auto_close, 'comments_log'].apply(lambda log: append_comment(log, "System", "Closed at Head Office (Not in latest pendency report)"))
        
    # Process uploaded rows
    max_id = pd.to_numeric(db_df['id'], errors='coerce').fillna(0).max() if 'id' in db_df.columns else 0
    
    new_rows = []
    
    for idx, row in df_up.iterrows():
        key = row['__key__']
        if key in set(db_df['__key__']):
            # Update
            db_idx = db_df[db_df['__key__'] == key].index[0]
            if str(db_df.loc[db_idx, 'is_goods_received']) == "0":
                for col in df_up.columns:
                    if col != '__key__':
                        db_df.loc[db_idx, col] = row[col]
                updated_count += 1
        else:
            # Insert
            max_id += 1
            row_dict = dict(row)
            row_dict['id'] = max_id
            row_dict['is_goods_received'] = "0"
            row_dict['is_invoice_received'] = "0"
            row_dict['goods_received_status'] = 'Pending'
            row_dict['store_invoice_status'] = 'Pending'
            new_rows.append(row_dict)
            inserted_count += 1
            
    if new_rows:
        db_df = pd.concat([db_df, pd.DataFrame(new_rows)], ignore_index=True)
        
    # Remove internal key and update
    db_df = db_df.drop(columns=['__key__'])
    update_sheet_df("grn_records", db_df)
    
    sync_management_users_from_records(db_df)
    
    return (inserted_count, updated_count, auto_completed_count)

def sync_management_users_from_records(grn_df: pd.DataFrame):
    mgmt_df = get_sheet_df("management_users")
    new_rows = []
    
    # Sumit
    if mgmt_df.empty or not (mgmt_df['username'] == 'sumit').any():
        new_rows.append({"username": "sumit", "password": "sumit123", "role": "mis_executive", "name": "Sumit (MIS)", "territory": "All Territories"})
        
    if 'rmm' in grn_df.columns:
        rmms = grn_df['rmm'].dropna().unique()
        for rmm in rmms:
            if str(rmm).strip() and str(rmm).strip().lower() != 'nan':
                username = str(rmm).strip().lower().replace(" ", "_")
                if mgmt_df.empty or not (mgmt_df['username'] == username).any():
                    new_rows.append({"username": username, "password": username, "role": "regional_manager", "name": str(rmm).strip(), "territory": str(rmm).strip()})
                    
    if 'cm' in grn_df.columns:
        cms = grn_df['cm'].dropna().unique()
        for cm in cms:
            if str(cm).strip() and str(cm).strip().lower() != 'nan':
                username = str(cm).strip().lower().replace(" ", "_")
                if mgmt_df.empty or not (mgmt_df['username'] == username).any():
                    new_rows.append({"username": username, "password": username, "role": "cluster_manager", "name": str(cm).strip(), "territory": str(cm).strip()})
                    
    if new_rows:
        if mgmt_df.empty:
            mgmt_df = pd.DataFrame(new_rows)
        else:
            mgmt_df = pd.concat([mgmt_df, pd.DataFrame(new_rows)], ignore_index=True)
        update_sheet_df("management_users", mgmt_df)
