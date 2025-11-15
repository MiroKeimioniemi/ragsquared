import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Flag, AuditChunkResult
from sqlalchemy import desc

session = get_session()

# Get latest audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if audit:
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    red = len([f for f in flags if f.flag_type == 'RED'])
    yellow = len([f for f in flags if f.flag_type == 'YELLOW'])
    green = len([f for f in flags if f.flag_type == 'GREEN'])
    
    print(f"=== Latest Audit ===")
    print(f"ID: {audit.external_id}")
    print(f"Status: {audit.status}")
    print(f"Chunks: {audit.chunk_completed}/{audit.chunk_total}")
    print(f"Flags: RED={red}, YELLOW={yellow}, GREEN={green}, Total={len(flags)}")
    
    # Check context usage
    results = session.query(AuditChunkResult).filter(
        AuditChunkResult.audit_id == audit.id
    ).limit(10).all()
    
    print(f"\n=== Context Usage (first 10 chunks) ===")
    for result in results:
        analysis = result.analysis or {}
        print(f"Chunk {result.chunk_index}: {result.context_token_count or 0} tokens, "
              f"flag={analysis.get('flag', 'N/A')}, "
              f"reg_refs={len(analysis.get('regulation_references', []))}, "
              f"reg_cites={len(analysis.get('citations', {}).get('regulation_sections', []))}")
else:
    print("No audits found")

