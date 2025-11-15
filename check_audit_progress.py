import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Document, Chunk, AuditChunkResult
from sqlalchemy import desc, func

session = get_session()

# Get the most recent audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if audit:
    print(f"Audit ID: {audit.id}")
    print(f"Status: {audit.status}")
    print(f"Chunks: {audit.chunk_completed}/{audit.chunk_total}")
    print(f"Started: {audit.started_at}")
    print(f"Completed: {audit.completed_at}")
    print(f"Failed: {audit.failed_at}")
    if audit.failure_reason:
        print(f"Failure: {audit.failure_reason[:200]}")
    
    # Get document
    doc = session.get(Document, audit.document_id)
    if doc:
        print(f"\nDocument Status: {doc.status}")
        
        # Count chunks
        total_chunks = session.query(Chunk).filter(Chunk.document_id == doc.id).count()
        print(f"Total chunks in DB: {total_chunks}")
        
        # Count audit chunk results
        results = session.query(AuditChunkResult).filter(AuditChunkResult.audit_id == audit.id).count()
        print(f"Audit chunk results: {results}")
        
        # Check if audit knows about chunks
        if audit.chunk_total == 0 and total_chunks > 0:
            print("\n⚠️  WARNING: Audit chunk_total is 0 but chunks exist!")
            print("   The audit needs to be updated with chunk count.")

