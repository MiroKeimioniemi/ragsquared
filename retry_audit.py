"""Retry a failed audit by running the compliance runner again."""

import sys
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit
from backend.app.services.compliance_runner import ComplianceRunner
from backend.app.config.settings import AppConfig
from sqlalchemy import desc

app = create_app()
with app.app_context():
    session = get_session()
    config = AppConfig()
    
    # Get the most recent failed audit
    audit = session.query(Audit).order_by(desc(Audit.created_at)).first()
    
    if not audit:
        print("No audits found")
        sys.exit(1)
    
    print(f"Retrying audit {audit.id} (External ID: {audit.external_id})")
    print(f"Current status: {audit.status}")
    print(f"Chunks processed: {audit.chunk_completed}/{audit.chunk_total}")
    
    # Reset status if it's failed
    if audit.status == "failed":
        audit.status = "queued"
        audit.failed_at = None
        audit.failure_reason = None
        session.commit()
        print("Reset audit status to 'queued'")
    
    # Run the compliance runner with rate limiting
    import time
    runner = ComplianceRunner(session, config)
    
    print("\nStarting audit processing...")
    print("Note: Processing with delays to avoid rate limits")
    print("This may take a while for large documents...\n")
    
    try:
        # Process in batches with delays
        max_chunks_per_batch = 5  # Process 5 chunks at a time
        delay_between_batches = 10  # Wait 10 seconds between batches
        
        while True:
            # Check current status
            session.refresh(audit)
            remaining = audit.chunk_total - audit.chunk_completed
            
            if remaining == 0 or audit.status in ("completed", "failed"):
                break
            
            print(f"Processing batch... ({audit.chunk_completed}/{audit.chunk_total} chunks done, {remaining} remaining)")
            
            result = runner.run(
                audit.id,
                max_chunks=max_chunks_per_batch,
            )
            
            print(f"  Processed {result.processed} chunks in this batch")
            print(f"  Status: {result.status}")
            
            if result.status == "failed":
                print(f"\n❌ Audit failed: {audit.failure_reason}")
                break
            
            if remaining > max_chunks_per_batch:
                print(f"  Waiting {delay_between_batches} seconds before next batch...")
                time.sleep(delay_between_batches)
        
        session.refresh(audit)
        print(f"\n✅ Audit completed!")
        print(f"   Final status: {audit.status}")
        print(f"   Chunks processed: {audit.chunk_completed}/{audit.chunk_total}")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Processing interrupted by user")
        session.refresh(audit)
        print(f"   Current status: {audit.status}")
        print(f"   Chunks processed: {audit.chunk_completed}/{audit.chunk_total}")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

