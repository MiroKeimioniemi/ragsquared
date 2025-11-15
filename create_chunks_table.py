"""Create chunks table with proper schema."""

import sqlite3
from pathlib import Path

db_path = Path("data/app.db")
if not db_path.exists():
    print("Database not found.")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check if chunks table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chunks'")
if cursor.fetchone():
    print("chunks table already exists")
    # Check if it has chunk_id
    cursor.execute("PRAGMA table_info(chunks)")
    cols = [row[1] for row in cursor.fetchall()]
    if "chunk_id" not in cols:
        print("Adding chunk_id column...")
        cursor.execute("ALTER TABLE chunks ADD COLUMN chunk_id VARCHAR(128)")
        conn.commit()
        print("Added chunk_id column")
else:
    print("Creating chunks table...")
    cursor.execute("""
        CREATE TABLE chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            chunk_id VARCHAR(128) NOT NULL UNIQUE,
            chunk_index INTEGER NOT NULL,
            section_path VARCHAR(512),
            parent_heading VARCHAR(255),
            content TEXT NOT NULL,
            token_count INTEGER,
            chunk_metadata TEXT,
            embedding_status VARCHAR(30) NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("""
        CREATE INDEX idx_chunks_doc_status ON chunks(document_id, embedding_status)
    """)
    conn.commit()
    print("Created chunks table with proper schema")

conn.close()
print("Done!")

