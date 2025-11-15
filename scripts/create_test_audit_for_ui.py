"""Create a test audit with sample data for UI testing."""

from __future__ import annotations

from backend.app import create_app
from backend.app.db.models import Audit, Citation, Document, Flag
from backend.app.db.session import get_session

app = create_app()

with app.app_context():
    session = get_session()
    
    # Create a test document
    doc = Document(
        original_filename="test_manual.pdf",
        stored_filename="test_manual.pdf",
        storage_path="uploads/test_manual.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="test" * 16,
        source_type="manual",
        organization="Test Organization",
        status="processed",
    )
    session.add(doc)
    session.flush()
    
    # Create a test audit
    audit = Audit(
        external_id="test-audit-ui",
        document_id=doc.id,
        status="completed",
        chunk_total=10,
        chunk_completed=10,
        is_draft=False,
    )
    session.add(audit)
    session.flush()
    
    # Create sample flags
    flag1 = Flag(
        audit_id=audit.id,
        chunk_id="chunk-1",
        flag_type="RED",
        severity_score=90,
        findings="Critical compliance issue: Missing required maintenance procedure documentation for Part-145.A.30.",
        gaps=["Missing procedure for personnel qualifications", "No documented training records"],
        recommendations=["Implement comprehensive training documentation", "Create personnel qualification tracking system"],
    )
    session.add(flag1)
    session.flush()
    
    flag2 = Flag(
        audit_id=audit.id,
        chunk_id="chunk-2",
        flag_type="YELLOW",
        severity_score=60,
        findings="Warning: Incomplete documentation for quality system requirements.",
        gaps=["Quality manual missing some sections"],
        recommendations=["Review and complete quality manual"],
    )
    session.add(flag2)
    session.flush()
    
    flag3 = Flag(
        audit_id=audit.id,
        chunk_id="chunk-3",
        flag_type="GREEN",
        severity_score=10,
        findings="Compliant: Record keeping procedures are well documented.",
        gaps=[],
        recommendations=[],
    )
    session.add(flag3)
    session.flush()
    
    # Create citations
    citation1 = Citation(
        flag_id=flag1.id,
        citation_type="regulation",
        reference="Part-145.A.30",
    )
    session.add(citation1)
    
    citation2 = Citation(
        flag_id=flag1.id,
        citation_type="regulation",
        reference="Part-145.A.35",
    )
    session.add(citation2)
    
    citation3 = Citation(
        flag_id=flag2.id,
        citation_type="regulation",
        reference="Part-145.A.25",
    )
    session.add(citation3)
    
    session.commit()
    
    print("\nTest audit created successfully!")
    print(f"\nAudit External ID: {audit.external_id}")
    print(f"Audit ID: {audit.id}")
    print(f"\nFlags created: 3 (1 RED, 1 YELLOW, 1 GREEN)")
    print("\nAccess the Review UI at:")
    print(f"   http://localhost:5000/review/{audit.external_id}")
    print(f"   or")
    print(f"   http://localhost:5000/review/{audit.id}")
    print()

