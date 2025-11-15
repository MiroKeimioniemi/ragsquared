import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Chunk, Document
from sqlalchemy import func

session = get_session()

# Get most recent document
from sqlalchemy import desc
doc = session.query(Document).order_by(desc(Document.created_at)).first()

if doc:
    print(f"Document ID: {doc.id}, Status: {doc.status}")
    
    # Get chunk status breakdown
    statuses = session.query(
        Chunk.embedding_status,
        func.count(Chunk.id).label('count')
    ).filter(
        Chunk.document_id == doc.id
    ).group_by(Chunk.embedding_status).all()
    
    print(f"\nChunk statuses:")
    for status, count in statuses:
        print(f"  {status}: {count}")
    
    # Check a few sample chunks
    chunks = session.query(Chunk).filter(Chunk.document_id == doc.id).limit(3).all()
    print(f"\nSample chunks:")
    for chunk in chunks:
        print(f"  Chunk {chunk.id}: status={chunk.embedding_status}, has_chunk_id={chunk.chunk_id is not None}")

