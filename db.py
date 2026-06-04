import sqlite3
import os

DB_PATH = "trends_grn.db"

def get_db_connection():
    """
    Establish a connection to the SQLite database.
    Configures WAL (Write-Ahead Logging) mode and timeouts for safe concurrent web requests.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database {DB_PATH} not found. Please run init_db.py first.")
        
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    
    # Enable WAL mode for high concurrency
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.OperationalError:
        pass
        
    return conn

def append_comment_log_in_transaction(cursor, record_id: int, sender: str, new_comment: str):
    """
    Appends a formatted comment to the record's comments_log within an active transaction.
    Format: 'sender: comment'
    """
    if not new_comment or not new_comment.strip():
        return
        
    cursor.execute("SELECT comments_log FROM grn_records WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    current_log = row[0] if row else None
    
    new_entry = f"{sender}: {new_comment.strip()}"
    if current_log:
        updated_log = f"{current_log}\n{new_entry}"
    else:
        updated_log = new_entry
        
    cursor.execute("UPDATE grn_records SET comments_log = ? WHERE id = ?", (updated_log, record_id))

# ==========================================
# AUTHENTICATION LOGIC
# ==========================================

def verify_store_code(store_code: str) -> bool:
    """
    Checks if the entered store code exists in the 'site' column of the database.
    Performs case-insensitive check by matching uppercase strings.
    """
    if not store_code:
        return False
        
    clean_store = store_code.strip().upper()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM grn_records WHERE UPPER(site) = ? LIMIT 1",
            (clean_store,)
        )
        row = cursor.fetchone()
        return row is not None
    except sqlite3.Error as e:
        print(f"Database error in verify_store_code: {e}")
        return False
    finally:
        conn.close()

def verify_vendor_login(vendor_code: str, password_input: str) -> bool:
    """
    Validates vendor login credentials against the vendor_users table.
    """
    if not vendor_code or not password_input:
        return False
        
    clean_vendor = vendor_code.strip().upper()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM vendor_users WHERE UPPER(vendor_code) = ? AND password = ?",
            (clean_vendor, password_input)
        )
        row = cursor.fetchone()
        return row is not None
    except sqlite3.Error as e:
        print(f"Database error in verify_vendor_login: {e}")
        return False
    finally:
        conn.close()

def verify_management_login(username_input: str, password_input: str):
    """
    Validates management login credentials against the management_users table.
    Returns a dict containing role, territory and name on success, or None on failure.
    """
    if not username_input or not password_input:
        return None
        
    clean_username = username_input.strip().lower()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, territory, name FROM management_users WHERE LOWER(username) = ? AND password = ?",
            (clean_username, password_input)
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    except sqlite3.Error as e:
        print(f"Database error in verify_management_login: {e}")
        return None
    finally:
        conn.close()

def update_vendor_password(vendor_code: str, new_password: str) -> bool:
    """
    Updates the password for a vendor and marks the password_changed flag.
    """
    if not vendor_code or not new_password:
        return False
        
    clean_vendor = vendor_code.strip().upper()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE vendor_users SET password = ?, password_changed = 1 WHERE UPPER(vendor_code) = ?",
            (new_password, clean_vendor)
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error in update_vendor_password: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
# STORE MANAGER DATA QUERIES & UPDATES
# ==========================================

def get_pending_grns(store_code: str):
    """
    Retrieves all pending GRNs for the given store code where goods have not been received yet.
    """
    if not store_code:
        return []
        
    clean_store = store_code.strip().upper()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM grn_records 
            WHERE UPPER(site) = ? AND is_goods_received = 0
            ORDER BY po_number ASC
            """,
            (clean_store,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_pending_grns: {e}")
        return []
    finally:
        conn.close()

def get_completed_grns(store_code: str):
    """
    Retrieves history of completed GRN updates for the given store code.
    """
    if not store_code:
        return []
        
    clean_store = store_code.strip().upper()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM grn_records 
            WHERE UPPER(site) = ? AND is_goods_received = 1
            ORDER BY id DESC
            """,
            (clean_store,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_completed_grns: {e}")
        return []
    finally:
        conn.close()

def update_grn_record(po_number: str, site: str, grn_number: str, invoice_file_path: str, sender: str, store_comments: str = None) -> bool:
    """
    Updates the database record for a completed GRN entry by PO Number and Site.
    Sets is_goods_received = 1, is_invoice_received = 1, store_invoice_status = 'Received', goods_received_status = 'Yes'.
    Appends comment to comments_log for all matching records.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE grn_records
            SET is_goods_received = 1,
                is_invoice_received = 1,
                grn_number = ?,
                invoice_file_path = ?,
                store_invoice_status = 'Received',
                goods_received_status = 'Yes'
            WHERE po_number = ? AND UPPER(site) = ?
            """,
            (grn_number, invoice_file_path, po_number, site.upper())
        )
        
        # Append comments
        if store_comments and store_comments.strip():
            cursor.execute("SELECT id FROM grn_records WHERE po_number = ? AND UPPER(site) = ?", (po_number, site.upper()))
            ids = cursor.fetchall()
            for row in ids:
                append_comment_log_in_transaction(cursor, row[0], sender, store_comments.strip())
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error in update_grn_record: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_store_invoice_status(po_number: str, site: str, invoice_status: str, sender: str, store_comments: str) -> bool:
    """
    Allows a store manager to log comments and report invoice status (e.g. 'Not Received' or 'Requested')
    when the goods themselves have been received physically (goods_received_status = 'Yes').
    Appends comments to comments_log for all matching records.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE grn_records
            SET store_invoice_status = ?,
                goods_received_status = 'Yes'
            WHERE po_number = ? AND UPPER(site) = ?
            """,
            (invoice_status, po_number, site.upper())
        )
        
        # Append comments
        if store_comments and store_comments.strip():
            cursor.execute("SELECT id FROM grn_records WHERE po_number = ? AND UPPER(site) = ?", (po_number, site.upper()))
            ids = cursor.fetchall()
            for row in ids:
                append_comment_log_in_transaction(cursor, row[0], sender, store_comments.strip())
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error in update_store_invoice_status: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_store_goods_received_issue(po_number: str, site: str, receipt_status: str, sender: str, store_comments: str) -> bool:
    """
    Logs store receipt status when goods are NOT fully received (No, Partially received, Have complaint in the work done).
    Sets is_goods_received = 0, store_invoice_status = 'Not Received'.
    Appends comments with a status prefix to comments_log for all matching records.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE grn_records
            SET goods_received_status = ?,
                store_invoice_status = 'Not Received',
                is_goods_received = 0
            WHERE po_number = ? AND UPPER(site) = ?
            """,
            (receipt_status, po_number, site.upper())
        )
        
        # Append comments with status indicator prefix (e.g., "[Partially received] Shortage details")
        if store_comments and store_comments.strip():
            prefixed_comment = f"[{receipt_status}] {store_comments.strip()}"
            cursor.execute("SELECT id FROM grn_records WHERE po_number = ? AND UPPER(site) = ?", (po_number, site.upper()))
            ids = cursor.fetchall()
            for row in ids:
                append_comment_log_in_transaction(cursor, row[0], sender, prefixed_comment)
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error in update_store_goods_received_issue: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
# VENDOR PORTAL DATA QUERIES & UPDATES
# ==========================================

def get_vendor_records(vendor_code: str):
    """
    Retrieves all records associated with a vendor code for display on the vendor portal.
    Includes unified comments_log.
    """
    if not vendor_code:
        return []
        
    clean_vendor = vendor_code.strip().upper()
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM grn_records 
            WHERE UPPER(vendor) = ?
            ORDER BY po_number ASC
            """,
            (clean_vendor,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_vendor_records: {e}")
        return []
    finally:
        conn.close()

def update_vendor_invoice_and_comments(po_number: str, vendor: str, sender: str, vendor_invoice_path: str = None, new_comment: str = None) -> bool:
    """
    Updates the invoice file path and appends vendor remarks to the comments_log for a given PO and Vendor.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Update vendor invoice path if provided
        if vendor_invoice_path is not None:
            cursor.execute(
                "UPDATE grn_records SET vendor_invoice_path = ? WHERE po_number = ? AND UPPER(vendor) = ?",
                (vendor_invoice_path, po_number, vendor.upper())
            )
            
        # 2. Append vendor comments to comments_log if provided
        if new_comment and new_comment.strip():
            cursor.execute("SELECT id FROM grn_records WHERE po_number = ? AND UPPER(vendor) = ?", (po_number, vendor.upper()))
            ids = cursor.fetchall()
            for row in ids:
                append_comment_log_in_transaction(cursor, row[0], sender, new_comment.strip())
            
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error in update_vendor_invoice_and_comments: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

# ==========================================
# MANAGEMENT PORTAL DATA QUERIES
# ==========================================

def get_management_pending_records(role: str, territory: str):
    """
    Retrieves all pending GRNs (is_goods_received = 0) within a manager's territory (cluster or region).
    """
    if not role or not territory:
        return []
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        if role == "cluster_manager":
            cursor.execute(
                """
                SELECT *
                FROM grn_records
                WHERE UPPER(cm) = ? AND is_goods_received = 0
                ORDER BY site ASC, po_number ASC
                """,
                (territory.upper(),)
            )
        elif role == "regional_manager":
            cursor.execute(
                """
                SELECT *
                FROM grn_records
                WHERE UPPER(rmm) = ? AND is_goods_received = 0
                ORDER BY site ASC, po_number ASC
                """,
                (territory.upper(),)
            )
        elif role == "mis_executive":
            # MIS Executive can view all records
            cursor.execute(
                """
                SELECT *
                FROM grn_records
                WHERE is_goods_received = 0
                ORDER BY site ASC, po_number ASC
                """
            )
        else:
            return []
            
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_management_pending_records: {e}")
        return []
    finally:
        conn.close()

def refresh_management_users_from_records(cursor):
    """
    Clears the management_users table and repopulates it based on the unique
    'rmm' and 'cm' values present in grn_records, plus the 'sumit' MIS account.
    """
    # 1. Clear existing management users
    cursor.execute("DELETE FROM management_users")
    
    # 2. Add Sumit MIS account
    cursor.execute(
        "INSERT INTO management_users (username, password, role, name, territory) VALUES (?, ?, ?, ?, ?)",
        ("sumit", "Sumit", "mis_executive", "Sumit (MIS)", "All Territories")
    )
    
    # 3. Get unique RMM names from grn_records
    cursor.execute("SELECT DISTINCT rmm FROM grn_records WHERE rmm IS NOT NULL AND rmm != ''")
    rmm_names = [r[0] for r in cursor.fetchall()]
    
    for rmm in rmm_names:
        username = str(rmm).strip().lower().replace(" ", "_")
        if username and username != "nan" and username != "sumit":
            cursor.execute(
                "INSERT OR IGNORE INTO management_users (username, password, role, name, territory) VALUES (?, ?, ?, ?, ?)",
                (username, username, "regional_manager", rmm, rmm)
            )
            
    # 4. Get unique CM names from grn_records
    cursor.execute("SELECT DISTINCT cm FROM grn_records WHERE cm IS NOT NULL AND cm != ''")
    cm_names = [r[0] for r in cursor.fetchall()]
    
    for cm in cm_names:
        username = str(cm).strip().lower().replace(" ", "_")
        if username and username != "nan" and username != "sumit":
            cursor.execute(
                "INSERT OR IGNORE INTO management_users (username, password, role, name, territory) VALUES (?, ?, ?, ?, ?)",
                (username, username, "cluster_manager", cm, cm)
            )

def sync_ho_pendency_data(df: pd.DataFrame) -> tuple:
    """
    Syncs the uploaded HO pendency report DataFrame with the SQLite database.
    Re-creates missing columns dynamically, updates values, inserts new ones,
    and auto-completes records no longer present in HO's report (since HO closed them).
    Returns (inserted_count, updated_count, auto_completed_count).
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Clean column names
        cleaned_cols = []
        for col in df.columns:
            col_clean = str(col).strip().lower()
            col_clean = col_clean.replace(" ", "_").replace("/", "_").replace(".", "").replace("-", "_")
            col_clean = col_clean.replace("&", "and").replace("(", "").replace(")", "")
            cleaned_cols.append(col_clean)
        df.columns = cleaned_cols
        
        # 2. Make datetimes string-safe
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].astype(str).replace("NaT", "").replace("nan", "")
                
        # 3. Handle NaNs in object columns
        for col in df.select_dtypes(include=['object']):
            df[col] = df[col].fillna("")
            
        # 4. Standard cleanups for primary search fields
        df['po_number'] = df['po_number'].astype(str).str.strip()
        df['vendor'] = df['vendor'].astype(str).str.strip()
        df['site'] = df['site'].astype(str).str.strip()
        df['article'] = df['article'].astype(str).str.strip()
        df['item'] = df['item'].astype(str).str.strip()
        
        # Numeric conversions
        df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
        df['grn_qty'] = pd.to_numeric(df['grn_qty'], errors='coerce').fillna(0).astype(int)
        df['pending_qty'] = pd.to_numeric(df['pending_qty'], errors='coerce').fillna(0).astype(int)
        df['net_value'] = pd.to_numeric(df['net_value'], errors='coerce').fillna(0.0)
        df['pending_value'] = pd.to_numeric(df['pending_value'], errors='coerce').fillna(0.0)
        df['days'] = pd.to_numeric(df['days'], errors='coerce').fillna(0).astype(int)
        
        # 5. Dynamically alter table to add columns that might be in uploaded file but not in DB
        cursor.execute("PRAGMA table_info(grn_records)")
        existing_db_cols = {row['name'] for row in cursor.fetchall()}
        
        for col in df.columns:
            if col not in existing_db_cols:
                # Add column dynamically to SQLite
                alter_sql = f'ALTER TABLE grn_records ADD COLUMN "{col}" TEXT'
                cursor.execute(alter_sql)
                existing_db_cols.add(col)
                print(f"Dynamically added column '{col}' to grn_records table.")
                
        conn.commit()
        
        # 6. Execute synchronization
        inserted_count = 0
        updated_count = 0
        uploaded_keys = set()
        
        # Fetch current DB records to check duplicates
        cursor.execute("SELECT id, po_number, item, is_goods_received FROM grn_records")
        db_records = cursor.fetchall()
        db_map = {(str(row['po_number']).strip(), str(row['item']).strip()): (row['id'], row['is_goods_received']) for row in db_records}
        
        for idx, row in df.iterrows():
            po_num = row['po_number']
            item = row['item']
            uploaded_keys.add((po_num, item))
            
            # Check if this PO line exists in DB
            if (po_num, item) in db_map:
                db_id, is_grned = db_map[(po_num, item)]
                
                # Only update details if not completed locally
                if is_grned == 0:
                    # Construct UPDATE query for sheet fields
                    set_clauses = []
                    params = []
                    for col in df.columns:
                        set_clauses.append(f'"{col}" = ?')
                        params.append(row[col])
                        
                    params.append(db_id)
                    update_sql = f'UPDATE grn_records SET {", ".join(set_clauses)} WHERE id = ?'
                    cursor.execute(update_sql, params)
                    updated_count += 1
            else:
                # Insert as a new pending record
                row_dict = dict(row)
                row_dict['is_goods_received'] = 0
                row_dict['is_invoice_received'] = 0
                row_dict['goods_received_status'] = 'Pending'
                row_dict['store_invoice_status'] = 'Pending'
                
                cols_to_insert = list(row_dict.keys())
                placeholders = ", ".join(["?"] * len(cols_to_insert))
                cols_str = ", ".join([f'"{c}"' for c in cols_to_insert])
                insert_vals = [row_dict[c] for c in cols_to_insert]
                
                cursor.execute(f'INSERT INTO grn_records ({cols_str}) VALUES ({placeholders})', insert_vals)
                inserted_count += 1
                
        # 7. Identify and auto-complete records closed at HO
        auto_completed_count = 0
        for (po_num, item), (db_id, is_grned) in db_map.items():
            if is_grned == 0 and (po_num, item) not in uploaded_keys:
                # This record is pending locally but missing from HO sheet -> HO closed it!
                sys_comment = "System: Closed at Head Office (Not in latest pendency report)"
                
                # Fetch current log
                cursor.execute("SELECT comments_log FROM grn_records WHERE id = ?", (db_id,))
                cur_log = cursor.fetchone()[0]
                updated_log = f"{cur_log}\n{sys_comment}" if cur_log else sys_comment
                
                cursor.execute(
                    """
                    UPDATE grn_records
                    SET is_goods_received = 1,
                        is_invoice_received = 1,
                        goods_received_status = 'Yes',
                        store_invoice_status = 'Received',
                        grn_number = 'Closed at HO',
                        comments_log = ?
                    WHERE id = ?
                    """,
                    (updated_log, db_id)
                )
                auto_completed_count += 1
                
        # 8. Refresh management logins based on new unique RMM/CM values
        refresh_management_users_from_records(cursor)
        
        conn.commit()
        return (inserted_count, updated_count, auto_completed_count)
    except Exception as e:
        print(f"Error in sync_ho_pendency_data: {e}")
        conn.rollback()
        raise e
    finally:
        conn.close()

def authenticate_user(user_id: str, password_input: str):
    """
    Unified authentication function. Detects the role based on the user_id:
    1. Management users: Checked in management_users.
    2. Vendor users: Checked in vendor_users.
    3. Store managers: Checked in grn_records (sites).
    
    Returns a dict with 'role' and details, or None on failure, or {'error': 'invalid_password'}
    """
    if not user_id or not password_input:
        return None
        
    clean_id = user_id.strip()
    clean_pwd = password_input.strip()
    
    conn = get_db_connection()
    try:
        # Create store_users table if not exists
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS store_users (
                store_code TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
            """
        )
        conn.commit()
        
        cursor = conn.cursor()
        
        # 1. Check management users (case-insensitive username)
        cursor.execute(
            "SELECT role, territory, name, password FROM management_users WHERE LOWER(username) = ?",
            (clean_id.lower(),)
        )
        mgmt_row = cursor.fetchone()
        if mgmt_row:
            if mgmt_row['password'] == clean_pwd:
                return {
                    "role": "management",
                    "username": clean_id.lower(),
                    "management_role": mgmt_row['role'],
                    "management_territory": mgmt_row['territory'],
                    "name": mgmt_row['name']
                }
            else:
                return {"error": "invalid_password"}
                
        # 2. Check vendor users (case-insensitive vendor code)
        cursor.execute(
            "SELECT password FROM vendor_users WHERE UPPER(vendor_code) = ?",
            (clean_id.upper(),)
        )
        vendor_row = cursor.fetchone()
        if vendor_row:
            if vendor_row['password'] == clean_pwd:
                return {
                    "role": "vendor",
                    "vendor_code": clean_id.upper()
                }
            else:
                return {"error": "invalid_password"}
                
        # 3. Check store managers
        # Check custom store manager password first
        cursor.execute(
            "SELECT password FROM store_users WHERE UPPER(store_code) = ?",
            (clean_id.upper(),)
        )
        store_user_row = cursor.fetchone()
        
        # Check if store exists at all in grn_records
        cursor.execute(
            "SELECT 1 FROM grn_records WHERE UPPER(site) = ? LIMIT 1",
            (clean_id.upper(),)
        )
        store_exists = cursor.fetchone() is not None
        
        if store_exists:
            if store_user_row:
                if store_user_row['password'] == clean_pwd:
                    return {
                        "role": "store_manager",
                        "store_code": clean_id.upper()
                    }
                else:
                    return {"error": "invalid_password"}
            else:
                # Default password is the store code itself (case-insensitive)
                if clean_pwd.upper() == clean_id.upper():
                    return {
                        "role": "store_manager",
                        "store_code": clean_id.upper()
                    }
                else:
                    return {"error": "invalid_password"}
                    
        # No user found
        return None
    except sqlite3.Error as e:
        print(f"Database error in authenticate_user: {e}")
        return None
    finally:
        conn.close()

def update_management_password(username: str, new_password: str) -> bool:
    """
    Updates the password for a management user.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE management_users SET password = ? WHERE LOWER(username) = ?",
            (new_password, username.strip().lower())
        )
        conn.commit()
        return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"Database error in update_management_password: {e}")
        return False
    finally:
        conn.close()

def update_store_password(store_code: str, new_password: str) -> bool:
    """
    Updates the custom password for a store manager.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS store_users (
                store_code TEXT PRIMARY KEY,
                password TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            "INSERT OR REPLACE INTO store_users (store_code, password) VALUES (?, ?)",
            (store_code.strip().upper(), new_password)
        )
        conn.commit()
        return True
    except sqlite3.Error as e:
        print(f"Database error in update_store_password: {e}")
        return False
    finally:
        conn.close()
