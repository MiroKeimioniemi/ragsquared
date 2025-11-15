"""Add all missing columns to chunks table."""

import sqlite3
from pathlib import Path

db_path = Path("data/app.db")
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Get existing columns
cursor.execute("PRAGMA table_info(chunks)")
existing_cols = {row[1]: row[2] for row in cursor.fetchall()}
print(f"Existing columns: {list(existing_cols.keys())}")

# Columns that should exist
required_columns = {
    'section_path': 'VARCHAR(512)',
    'parent_heading': 'VARCHAR(255)',
}

# Add missing columns
for col_name, col_type in required_columns.items():
    if col_name not in existing_cols:
        print(f"Adding {col_name} column...")
        cursor.execute(f"ALTER TABLE chunks ADD COLUMN {col_name} {col_type}")
        conn.commit()
        print(f"Added {col_name} column")
    else:
        print(f"{col_name} column already exists")

conn.close()
print("Done!")

