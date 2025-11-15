import sys
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Flag
from sqlalchemy import desc

session = get_session()

# Get the most recent audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if audit:
    print(f"Audit ID: {audit.id}, Status: {audit.status}")
    
    # Get flags
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    print(f"\nFlags found: {len(flags)}")
    
    for flag in flags[:5]:  # Show first 5
        print(f"\nFlag {flag.id}:")
        print(f"  Type: {flag.flag_type}")
        print(f"  Severity: {flag.severity_score}")
        print(f"  Findings: {flag.findings[:100]}...")
        print(f"  Citations: {len(flag.citations)}")

