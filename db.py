import streamlit as st

def get_backend():
    """
    Dynamically loads either the Google Sheets backend or the SQLite backend
    based on the presence of Google credentials in Streamlit secrets.
    """
    use_gsheets = False
    
    # Safely check if secrets exist
    if hasattr(st, "secrets") and "gcp_service_account" in st.secrets and "spreadsheet_id" in st.secrets:
        use_gsheets = True

    if use_gsheets:
        try:
            import db_gsheets as backend
            # st.toast("Connected to Google Sheets ☁️")
            return backend
        except Exception as e:
            print(f"Failed to load Google Sheets backend: {e}")
            print("Falling back to local SQLite backend.")
            import db_sqlite as backend
            return backend
    else:
        import db_sqlite as backend
        return backend

# Load the backend singleton module
backend = get_backend()

# ==========================================
# RE-EXPORT PUBLIC API
# ==========================================

authenticate_user = backend.authenticate_user
update_management_password = backend.update_management_password
update_store_password = backend.update_store_password
update_vendor_password = backend.update_vendor_password

get_pending_grns = backend.get_pending_grns
get_completed_grns = backend.get_completed_grns
update_grn_record = backend.update_grn_record
update_store_invoice_status = backend.update_store_invoice_status
update_store_goods_received_issue = backend.update_store_goods_received_issue

get_vendor_records = backend.get_vendor_records
update_vendor_invoice_and_comments = backend.update_vendor_invoice_and_comments

get_management_pending_records = backend.get_management_pending_records
sync_ho_pendency_data = backend.sync_ho_pendency_data
