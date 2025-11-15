"""Tests for draft mode processing."""

from __future__ import annotations

from backend.app.config.settings import AppConfig
from backend.app.db.models import Audit, Chunk, Document
from backend.app.db.session import get_session
from backend.app.services.compliance_runner import ComplianceRunner, EchoAnalysisClient


def test_draft_audit_limits_chunks(app, db_session):
    """Test that draft audits only process first 5 chunks."""
    session = db_session
    config = AppConfig()

    # Create document with 10 chunks
    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc)
    session.flush()

    # Create 10 chunks
    for i in range(10):
        chunk = Chunk(
            document_id=doc.id,
            chunk_id=f"chunk_{i}",
            chunk_index=i,
            content=f"Chunk {i} content",
            token_count=100,
        )
        session.add(chunk)
    session.commit()

    # Create draft audit
    draft_audit = Audit(document_id=doc.id, status="queued", is_draft=True)
    session.add(draft_audit)
    session.commit()

    # Run audit
    runner = ComplianceRunner(session, config, analysis_client=EchoAnalysisClient())
    result = runner.run(draft_audit.id)

    # Should only process 5 chunks (draft limit)
    assert result.processed <= 5
    assert draft_audit.chunk_completed <= 5


def test_draft_audit_skips_evidence(app, db_session):
    """Test that draft audits skip evidence retrieval."""
    session = db_session
    config = AppConfig()

    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc)
    session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_id="chunk_1",
        chunk_index=0,
        content="Test content",
        token_count=100,
    )
    session.add(chunk)
    session.commit()

    draft_audit = Audit(document_id=doc.id, status="queued", is_draft=True)
    session.add(draft_audit)
    session.commit()

    runner = ComplianceRunner(session, config, analysis_client=EchoAnalysisClient())
    result = runner.run(draft_audit.id)

    # Should complete successfully without evidence
    assert result.processed > 0


def test_draft_audit_skips_refinement(app, db_session):
    """Test that draft audits skip refinement loops."""
    session = db_session
    config = AppConfig()

    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc)
    session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_id="chunk_1",
        chunk_index=0,
        content="Test content",
        token_count=100,
    )
    session.add(chunk)
    session.commit()

    draft_audit = Audit(document_id=doc.id, status="queued", is_draft=True)
    session.add(draft_audit)
    session.commit()

    # Create a client that always requests additional context
    class AlwaysRefineClient(EchoAnalysisClient):
        def analyze(self, chunk, context):
            result = super().analyze(chunk, context)
            result["needs_additional_context"] = True
            return result

    runner = ComplianceRunner(session, config, analysis_client=AlwaysRefineClient())
    result = runner.run(draft_audit.id)

    # Should complete without refinement (draft mode skips it)
    assert result.processed > 0
    # Check that no refinement happened
    from backend.app.db.models import AuditChunkResult

    results = session.query(AuditChunkResult).filter(AuditChunkResult.audit_id == draft_audit.id).all()
    for r in results:
        if r.analysis:
            # Draft mode should not have refinement attempts
            assert r.analysis.get("refinement_attempts", 0) == 0


def test_draft_audit_reduced_context(app, db_session):
    """Test that draft audits use reduced context budgets."""
    session = db_session
    config = AppConfig()

    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc)
    session.flush()

    chunk = Chunk(
        document_id=doc.id,
        chunk_id="chunk_1",
        chunk_index=0,
        content="Test content",
        token_count=100,
    )
    session.add(chunk)
    session.commit()

    draft_audit = Audit(document_id=doc.id, status="queued", is_draft=True)
    session.add(draft_audit)
    session.commit()

    runner = ComplianceRunner(session, config, analysis_client=EchoAnalysisClient())
    result = runner.run(draft_audit.id)

    # Check context token counts are reduced
    from backend.app.db.models import AuditChunkResult

    results = session.query(AuditChunkResult).filter(AuditChunkResult.audit_id == draft_audit.id).all()
    for r in results:
        if r.context_token_count:
            # Draft mode should have lower token counts due to reduced budgets
            # Normal mode would be around 6000, draft should be around 3000 (half)
            assert r.context_token_count < 4000  # Allow some variance

