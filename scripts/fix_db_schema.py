"""Fix database schema by adding missing columns."""

import sqlite3
from pathlib import Path

db_path = Path("data/app.db")
if not db_path.exists():
    print("Database not found. Run migrations first.")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check existing columns
cursor.execute("PRAGMA table_info(documents)")
existing_cols = [row[1] for row in cursor.fetchall()]
print(f"Existing columns: {existing_cols}")

# Add missing columns
if "source_type" not in existing_cols:
    cursor.execute("ALTER TABLE documents ADD COLUMN source_type VARCHAR(20) DEFAULT 'manual'")
    print("Added source_type column")
else:
    print("source_type column already exists")

if "organization" not in existing_cols:
    cursor.execute("ALTER TABLE documents ADD COLUMN organization VARCHAR(255)")
    print("Added organization column")
else:
    print("organization column already exists")

conn.commit()
conn.close()
print("Database schema updated!")

