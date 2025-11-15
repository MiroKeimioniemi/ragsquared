import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Document
from sqlalchemy import desc

session = get_session()

# Get the most recent audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if audit:
    print(f"Audit ID: {audit.id}")
    print(f"External ID: {audit.external_id}")
    print(f"Status: {audit.status}")
    print(f"Document ID: {audit.document_id}")
    print(f"Created: {audit.created_at}")
    print(f"Started: {audit.started_at}")
    print(f"Completed: {audit.completed_at}")
    print(f"Failed: {audit.failed_at}")
    if audit.failure_reason:
        print(f"Failure Reason: {audit.failure_reason}")
    print(f"Chunks: {audit.chunk_completed}/{audit.chunk_total}")
    
    # Get document info
    doc = session.get(Document, audit.document_id)
    if doc:
        print(f"\nDocument: {doc.original_filename}")
        print(f"Document Status: {doc.status}")
        print(f"Source Type: {doc.source_type}")
else:
    print("No audits found")

