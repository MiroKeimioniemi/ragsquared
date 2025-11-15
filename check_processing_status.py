import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Document, Chunk
from sqlalchemy import desc

session = get_session()

# Get the most recent audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if audit:
    print(f"Audit ID: {audit.id}")
    print(f"Status: {audit.status}")
    print(f"Chunks: {audit.chunk_completed}/{audit.chunk_total}")
    
    # Get document
    doc = session.get(Document, audit.document_id)
    if doc:
        print(f"\nDocument Status: {doc.status}")
        
        # Count actual chunks in database
        chunk_count = session.query(Chunk).filter(Chunk.document_id == doc.id).count()
        print(f"Chunks in database: {chunk_count}")
        
        # Check chunk statuses
        pending = session.query(Chunk).filter(
            Chunk.document_id == doc.id,
            Chunk.embedding_status == "pending"
        ).count()
        completed = session.query(Chunk).filter(
            Chunk.document_id == doc.id,
            Chunk.embedding_status == "completed"
        ).count()
        print(f"  - Pending: {pending}")
        print(f"  - Completed: {completed}")
else:
    print("No audits found")

