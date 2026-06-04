import os
import pandas as pd
import sqlite3
import db

def init_database():
    excel_path = "HO_GRN_pendency.xlsx"
    db_path = "trends_grn.db"
    
    if not os.path.exists(excel_path):
        print(f"Error: {excel_path} not found in the current directory.")
        return
        
    print(f"Reading data from sheet 'GRN' in {excel_path}...")
    df = pd.read_excel(excel_path, sheet_name='GRN')
    
    # Clean up column names: strip spaces, convert to lowercase, replace spaces/slashes/dots with underscores
    cleaned_cols = []
    for col in df.columns:
        col_clean = col.strip().lower()
        col_clean = col_clean.replace(" ", "_")
        col_clean = col_clean.replace("/", "_")
        col_clean = col_clean.replace(".", "")
        col_clean = col_clean.replace("-", "_")
        col_clean = col_clean.replace("&", "and")
        col_clean = col_clean.replace("(", "").replace(")", "")
        cleaned_cols.append(col_clean)
        
    df.columns = cleaned_cols
    
    # Convert any datetime/timestamp columns to string
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str).replace("NaT", "").replace("nan", "")
            
    # Clean data fields to correct data types
    df['po_number'] = df['po_number'].astype(str).str.strip()
    df['vendor'] = df['vendor'].astype(str).str.strip()
    df['site'] = df['site'].astype(str).str.strip()
    df['article'] = df['article'].astype(str).str.strip()
    df['item'] = df['item'].astype(str).str.strip()
    
    # For numeric columns, fill NaN with defaults or 0
    df['price'] = pd.to_numeric(df['price'], errors='coerce').fillna(0.0)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    df['grn_qty'] = pd.to_numeric(df['grn_qty'], errors='coerce').fillna(0).astype(int)
    df['pending_qty'] = pd.to_numeric(df['pending_qty'], errors='coerce').fillna(0).astype(int)
    df['net_value'] = pd.to_numeric(df['net_value'], errors='coerce').fillna(0.0)
    df['pending_value'] = pd.to_numeric(df['pending_value'], errors='coerce').fillna(0.0)
    df['days'] = pd.to_numeric(df['days'], errors='coerce').fillna(0).astype(int)
    
    # Write to SQLite
    print(f"Connecting to SQLite database {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Drop existing tables
    cursor.execute("DROP TABLE IF EXISTS grn_records")
    cursor.execute("DROP TABLE IF EXISTS vendor_users")
    cursor.execute("DROP TABLE IF EXISTS management_users")
    conn.commit()
    
    # Recreate table structures dynamically based on Excel columns
    print("Creating 'grn_records' table dynamically...")
    col_types = {col: "TEXT" for col in df.columns}
    col_types['price'] = "REAL"
    col_types['quantity'] = "INTEGER"
    col_types['grn_qty'] = "INTEGER"
    col_types['pending_qty'] = "INTEGER"
    col_types['net_value'] = "REAL"
    col_types['pending_value'] = "REAL"
    col_types['days'] = "INTEGER"
    
    tracking_cols = {
        "is_goods_received": "INTEGER DEFAULT 0",
        "is_invoice_received": "INTEGER DEFAULT 0",
        "grn_number": "TEXT NULL",
        "invoice_file_path": "TEXT NULL",
        "vendor_invoice_path": "TEXT NULL",
        "store_invoice_status": "TEXT DEFAULT 'Pending'",
        "goods_received_status": "TEXT DEFAULT 'Pending'",
        "comments_log": "TEXT NULL",
        "cm": "TEXT NULL"
    }
    
    col_defs = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
    for col, t in col_types.items():
        col_defs.append(f'"{col}" {t}')
    for col, t in tracking_cols.items():
        col_defs.append(f'"{col}" {t}')
        
    create_records_sql = f"CREATE TABLE grn_records ({', '.join(col_defs)})"
    cursor.execute(create_records_sql)
    
    # Replace NaN values in string columns with empty strings before saving to database
    for col in df.select_dtypes(include=['object']):
        df[col] = df[col].fillna("")
        
    # Insert dataframe records using SQL
    cols = df.columns.tolist()
    placeholders = ", ".join(["?"] * len(cols))
    cols_str = ", ".join([f'"{c}"' for c in cols])
    cursor.executemany(f"INSERT INTO grn_records ({cols_str}) VALUES ({placeholders})", df.values.tolist())
    
    # Create indexes
    cursor.execute("CREATE INDEX idx_site ON grn_records (site)")
    cursor.execute("CREATE INDEX idx_vendor ON grn_records (vendor)")
    cursor.execute("CREATE INDEX idx_po_item ON grn_records (po_number, item)")
    cursor.execute("CREATE INDEX idx_rmm ON grn_records (rmm)")
    cursor.execute("CREATE INDEX idx_cm ON grn_records (cm)")
    conn.commit()
    print("Database table 'grn_records' populated.")
    
    # Create vendor credentials table
    print("Creating 'vendor_users' table for vendor logins...")
    create_vendors_sql = """
    CREATE TABLE vendor_users (
        vendor_code TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        password_changed INTEGER DEFAULT 0
    )
    """
    cursor.execute(create_vendors_sql)
    
    cursor.execute("SELECT DISTINCT vendor FROM grn_records WHERE vendor IS NOT NULL AND vendor != ''")
    vendors = [r[0] for r in cursor.fetchall()]
    
    cursor.executemany(
        "INSERT OR IGNORE INTO vendor_users (vendor_code, password, password_changed) VALUES (?, ?, 0)",
        [(v, v) for v in vendors]
    )
    conn.commit()
    
    # Create management credentials table
    print("Creating 'management_users' table for management logins...")
    create_mgmt_sql = """
    CREATE TABLE management_users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        name TEXT NOT NULL,
        territory TEXT NOT NULL
    )
    """
    cursor.execute(create_mgmt_sql)
    conn.commit()
    
    # Dynamically seed management accounts (RMM, CM, and Sumit) based on actual Excel values
    print("Seeding management accounts dynamically based on spreadsheet values...")
    db.refresh_management_users_from_records(cursor)
    conn.commit()
    print("Database table 'management_users' populated dynamically.")
    
    cursor.execute("SELECT COUNT(*) FROM grn_records")
    records_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM vendor_users")
    vendors_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM management_users")
    mgmt_count = cursor.fetchone()[0]
    
    print(f"Successfully loaded {records_count} PO records, {vendors_count} vendor users, and {mgmt_count} management users.")
    conn.close()
    print("Database initialization completed successfully!")

if __name__ == "__main__":
    init_database()
