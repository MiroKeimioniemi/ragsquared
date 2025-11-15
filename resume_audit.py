#!/usr/bin/env python3
"""Resume processing a stuck audit."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.config.settings import AppConfig
from backend.app.services.compliance_runner import ComplianceRunner

app = create_app()
with app.app_context():
    session = get_session()
    config = AppConfig()
    
    # Get the latest running audit
    from backend.app.db.models import Audit
    audit = session.query(Audit).filter(Audit.status == "running").order_by(Audit.created_at.desc()).first()
    
    if not audit:
        print("No running audit found.")
        # Try to get the latest audit regardless of status
        audit = session.query(Audit).order_by(Audit.created_at.desc()).first()
        if audit:
            print(f"Found audit with status '{audit.status}': {audit.external_id}")
        else:
            print("No audits found.")
            sys.exit(1)
    
    print(f"Resuming audit: {audit.external_id}")
    print(f"Status: {audit.status}")
    print(f"Progress: {audit.chunk_completed}/{audit.chunk_total} chunks")
    
    # Create runner and resume
    runner = ComplianceRunner(session, config)
    result = runner.run(
        audit.external_id,
        max_chunks=None,  # Process all remaining chunks
        include_evidence=not audit.is_draft,
    )
    
    print(f"\nResult:")
    print(f"  Processed: {result.processed} chunks")
    print(f"  Remaining: {result.remaining} chunks")
    print(f"  Status: {result.status}")

