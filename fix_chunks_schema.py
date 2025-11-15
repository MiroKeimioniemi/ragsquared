"""Fix chunks table schema by adding missing chunk_id column."""

import sqlite3
from pathlib import Path

db_path = Path("data/app.db")
if not db_path.exists():
    print("Database not found.")
    exit(1)

conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

# Check existing columns in chunks table
try:
    cursor.execute("PRAGMA table_info(chunks)")
    existing_cols = [row[1] for row in cursor.fetchall()]
    print(f"Existing chunks columns: {existing_cols}")
    
    # Add missing chunk_id column if it doesn't exist
    if "chunk_id" not in existing_cols:
        print("Adding chunk_id column to chunks table...")
        # First, check if there are any existing rows
        cursor.execute("SELECT COUNT(*) FROM chunks")
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Generate chunk_id for existing rows based on document_id and id
            cursor.execute("""
                ALTER TABLE chunks ADD COLUMN chunk_id_temp VARCHAR(128)
            """)
            cursor.execute("""
                UPDATE chunks SET chunk_id_temp = 'chunk_' || document_id || '_' || id
            """)
            # Drop old table and recreate with chunk_id
            cursor.execute("DROP TABLE chunks")
        else:
            # No data, safe to add column
            cursor.execute("""
                ALTER TABLE chunks ADD COLUMN chunk_id VARCHAR(128)
            """)
            conn.commit()
            print("Added chunk_id column")
    else:
        print("chunk_id column already exists")
    
    # Recreate table with proper schema if we dropped it
    if "chunk_id" not in existing_cols and count > 0:
        cursor.execute("""
            CREATE TABLE chunks_new (
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
            INSERT INTO chunks_new 
            SELECT id, document_id, chunk_id_temp, chunk_index, section_path, 
                   parent_heading, content, token_count, chunk_metadata, 
                   embedding_status, created_at, updated_at
            FROM chunks
        """)
        cursor.execute("DROP TABLE chunks")
        cursor.execute("ALTER TABLE chunks_new RENAME TO chunks")
        cursor.execute("""
            CREATE INDEX idx_chunks_doc_status ON chunks(document_id, embedding_status)
        """)
        conn.commit()
        print("Recreated chunks table with chunk_id column")
    
except sqlite3.OperationalError as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    conn.close()

print("Database schema check complete!")

