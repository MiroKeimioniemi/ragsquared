#!/usr/bin/env python3
"""Run audit for MOE document and monitor RAG usage."""

import sys
from pathlib import Path
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Document, Audit
from backend.app.config.settings import AppConfig
from backend.app.services.compliance_runner import ComplianceRunner
from sqlalchemy import desc

app = create_app()
with app.app_context():
    session = get_session()
    
    # Find latest document (should be MOE)
    doc = session.query(Document).order_by(desc(Document.created_at)).first()
    
    if not doc:
        print("[ERROR] No documents found. Please upload a document first.")
        sys.exit(1)
    
    print(f"Found document: {doc.original_filename}")
    print(f"Document ID: {doc.id} (external: {doc.external_id})")
    print(f"Status: {doc.status}")
    
    # Find or create audit
    audit = session.query(Audit).filter(
        Audit.document_id == doc.id
    ).order_by(desc(Audit.created_at)).first()
    
    if not audit or audit.status in ['completed', 'failed']:
        # Create new audit
        print("\nCreating new audit...")
        audit = Audit(
            document_id=doc.id,
            is_draft=False,
            status="queued",
        )
        session.add(audit)
        session.commit()
        session.refresh(audit)
        print(f"[OK] Created audit: {audit.external_id}")
    else:
        print(f"\nUsing existing audit: {audit.external_id}")
        print(f"Status: {audit.status}")
    
    # Run the audit
    print(f"\n{'='*60}")
    print("Running audit with RAG monitoring...")
    print(f"{'='*60}\n")
    print("Watch for these log messages:")
    print("  [OK] INFO: RAG query: Searching 'regulation_chunks'...")
    print("  [OK] INFO: RAG query: Found X/Y similar chunks...")
    print("  [OK] INFO: Context built for chunk X: Y regulations, Z guidance...")
    print("  [WARN] WARNING: No results from 'regulation_chunks'... (if collections empty)")
    print(f"\n{'='*60}\n")
    
    config = AppConfig()
    runner = ComplianceRunner(session, config)
    
    result = runner.run(
        audit.external_id,  # audit_id as positional argument
        max_chunks=None,  # Process all chunks
        include_evidence=True,
    )
    
    print(f"\n{'='*60}")
    print("Audit Complete!")
    print(f"{'='*60}")
    print(f"Processed: {result.processed} chunks")
    print(f"Remaining: {result.remaining} chunks")
    print(f"Status: {result.status}")
    
    # Refresh to get latest flag counts
    session.refresh(audit)
    from backend.app.db.models import Flag
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    red = len([f for f in flags if f.flag_type == 'RED'])
    yellow = len([f for f in flags if f.flag_type == 'YELLOW'])
    green = len([f for f in flags if f.flag_type == 'GREEN'])
    
    print(f"\nFlags found:")
    print(f"  RED: {red}")
    print(f"  YELLOW: {yellow}")
    print(f"  GREEN: {green}")
    print(f"  Total: {len(flags)}")
    
    if audit.chunk_total > 100 and (red + yellow) < 10:
        print(f"\n[WARN] WARNING: Only {red + yellow} flags for {audit.chunk_total} chunks!")
        print("   This suggests RAG may not be working. Check logs above for warnings.")

