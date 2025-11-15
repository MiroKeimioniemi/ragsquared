"""Test dashboard query directly."""
import sys
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit, Document
from sqlalchemy import select, desc

app = create_app()
with app.app_context():
    session = get_session()
    
    # Get query parameters (simulating request.args)
    status_filter = None
    is_draft = None
    limit = 50
    
    # Build query (same as dashboard route)
    query = select(Audit)
    
    if status_filter:
        query = query.where(Audit.status == status_filter)
    
    if is_draft is not None:
        is_draft_bool = str(is_draft).lower() in ("true", "1", "yes")
        query = query.where(Audit.is_draft == is_draft_bool)
    
    # Order by created_at descending
    query = query.order_by(desc(Audit.created_at)).limit(limit)
    
    audits = session.execute(query).scalars().all()
    print(f"Query returned: {len(audits)} audits")
    
    # Get documents and scores for each audit (same as dashboard route)
    from backend.app.services.compliance_score import get_flag_summary
    from backend.app.db.models import Flag
    
    audit_list = []
    for audit in audits:
        document = session.get(Document, audit.document_id) if audit.document_id else None
        print(f"  Audit {audit.id}: document_id={audit.document_id}, document={document.original_filename if document else None}")
        
        # Get flag summary if audit is completed
        flag_summary = None
        if audit.status == "completed":
            flags = session.execute(
                select(Flag).where(Flag.audit_id == audit.id)
            ).scalars().all()
            flag_summary = get_flag_summary(list(flags))
        
        audit_list.append({
            "audit": audit,
            "document": document,
            "flag_summary": flag_summary,
        })
    
    print(f"\nAudit list length: {len(audit_list)}")
    print(f"Should show on dashboard: {'YES' if audit_list else 'NO'}")

