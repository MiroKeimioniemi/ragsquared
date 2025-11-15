"""Clear flags for an audit to allow re-processing with updated prompts."""

import sys
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit, Flag, AuditChunkResult
from sqlalchemy import desc

app = create_app()
with app.app_context():
    session = get_session()
    
    # Get the most recent audit
    audit = session.query(Audit).order_by(desc(Audit.created_at)).first()
    
    if not audit:
        print("No audits found")
        sys.exit(1)
    
    print(f"Clearing flags for audit {audit.id} (External ID: {audit.external_id})")
    
    # Delete flags
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    flag_count = len(flags)
    for flag in flags:
        session.delete(flag)
    
    # Delete chunk results
    results = session.query(AuditChunkResult).filter(AuditChunkResult.audit_id == audit.id).all()
    result_count = len(results)
    for result in results:
        session.delete(result)
    
    # Reset audit status
    audit.status = "queued"
    audit.chunk_completed = 0
    audit.failed_at = None
    audit.failure_reason = None
    
    session.commit()
    
    print(f"✅ Cleared {flag_count} flags and {result_count} chunk results")
    print(f"✅ Reset audit status to 'queued'")
    print(f"\nYou can now re-run the audit with: python retry_audit.py")

