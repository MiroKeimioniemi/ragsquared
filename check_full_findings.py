import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Flag, Chunk
from sqlalchemy import desc

session = get_session()

# Get the most recent audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if audit:
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    print(f"Found {len(flags)} flags for audit {audit.id}\n")
    
    for flag in flags:
        print(f"=" * 80)
        print(f"Flag {flag.id}: {flag.flag_type} (Severity: {flag.severity_score})")
        print(f"Chunk ID: {flag.chunk_id}")
        
        # Get the chunk content
        chunk = session.query(Chunk).filter(Chunk.chunk_id == flag.chunk_id).first()
        if chunk:
            print(f"\nChunk Content (first 200 chars):")
            print(chunk.content[:200] + "...")
        
        print(f"\nFindings:")
        print(flag.findings)
        print(f"\nGaps: {flag.gaps}")
        print(f"Recommendations: {flag.recommendations}")
        print(f"\nCitations:")
        for citation in flag.citations:
            print(f"  - {citation.citation_type}: {citation.reference}")
        print()

