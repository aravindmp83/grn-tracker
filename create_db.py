import pandas as pd
import sqlite3

# 1. Define file paths
csv_file = 'GRN 2 Jun 2026.xlsx - Sheet1.csv'
db_file = 'trends_grn.db'

# 2. Read the CSV data
print(f"Reading data from {csv_file}...")
df = pd.read_csv(csv_file)

# 3. Add the new application-specific columns with default values
df['is_goods_received'] = 0
df['is_invoice_received'] = 0
df['grn_number'] = None
df['invoice_file_path'] = None

# 4. Connect to SQLite (this creates the .db file automatically)
print(f"Creating database {db_file}...")
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# 5. Write the data to a new table named 'grn_records'
df.to_sql('grn_records', conn, if_exists='replace', index=False)

# 6. Create an index on the 'Site' column (Store Code) 
print("Creating index on Site (Store Code)...")
cursor.execute('CREATE INDEX idx_site ON grn_records(Site)')

# Commit changes and close the connection
conn.commit()
conn.close()

print("Database 'trends_grn.db' created successfully!")
