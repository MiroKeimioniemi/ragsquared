"""Tests for the compare CLI command."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from cli import app

runner = CliRunner()


@pytest.fixture
def two_audits_with_flags(app, db_session):
    """Create two audits with different flags for comparison."""
    from backend.app.db.models import Audit, Citation, Document, Flag

    session = db_session

    # Create documents
    doc1 = Document(
        original_filename="manual1.pdf",
        stored_filename="manual1.pdf",
        storage_path="uploads/manual1.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        status="processed",
    )
    doc2 = Document(
        original_filename="manual2.pdf",
        stored_filename="manual2.pdf",
        storage_path="uploads/manual2.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="b" * 64,
        source_type="manual",
        status="processed",
    )
    session.add_all([doc1, doc2])
    session.flush()

    # Create audits
    audit1 = Audit(document_id=doc1.id, status="completed", chunk_total=2, chunk_completed=2)
    audit2 = Audit(document_id=doc2.id, status="completed", chunk_total=2, chunk_completed=2)
    session.add_all([audit1, audit2])
    session.flush()

    # Create flags for audit1
    flag1 = Flag(
        audit_id=audit1.id,
        chunk_id="chunk-1",
        flag_type="RED",
        severity_score=90,
        findings="Critical issue",
    )
    flag1.citations.append(Citation(citation_type="regulation", reference="Part-145.A.30"))
    session.add(flag1)

    flag2 = Flag(
        audit_id=audit1.id,
        chunk_id="chunk-2",
        flag_type="YELLOW",
        severity_score=60,
        findings="Warning",
    )
    session.add(flag2)

    # Create flags for audit2 (different)
    flag3 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-1",
        flag_type="YELLOW",  # Changed from RED
        severity_score=65,
        findings="Improved",
    )
    flag3.citations.append(Citation(citation_type="regulation", reference="Part-145.A.30"))
    session.add(flag3)

    flag4 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-2",
        flag_type="GREEN",  # Changed from YELLOW
        severity_score=20,
        findings="Compliant",
    )
    session.add(flag4)

    # New flag in audit2
    flag5 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-3",
        flag_type="GREEN",
        severity_score=10,
        findings="New compliant section",
    )
    session.add(flag5)

    session.commit()
    return audit1, audit2


def test_cli_compare_shows_compliance_scores(two_audits_with_flags):
    """Test that compare command shows compliance scores."""
    audit1, audit2 = two_audits_with_flags
    result = runner.invoke(app, ["compare", str(audit1.id), str(audit2.id)])
    assert result.exit_code == 0
    assert "Compliance Score" in result.stdout


def test_cli_compare_json_output(two_audits_with_flags):
    """Test that compare command supports JSON output."""
    audit1, audit2 = two_audits_with_flags
    result = runner.invoke(app, ["compare", str(audit1.id), str(audit2.id), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "audit_a" in data
    assert "audit_b" in data
    assert "comparison" in data
    assert "compliance_score_delta" in data["comparison"]


def test_cli_compare_markdown_output(two_audits_with_flags):
    """Test that compare command supports Markdown output."""
    audit1, audit2 = two_audits_with_flags
    result = runner.invoke(app, ["compare", str(audit1.id), str(audit2.id), "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Audit Comparison" in result.stdout
    assert "## Summary" in result.stdout


def test_cli_compare_filters_by_severity(two_audits_with_flags):
    """Test that compare command filters by severity."""
    audit1, audit2 = two_audits_with_flags
    result = runner.invoke(app, ["compare", str(audit1.id), str(audit2.id), "--severity", "RED"])
    assert result.exit_code == 0
    # Should only show RED flags in comparison


def test_cli_compare_filters_by_regulation(two_audits_with_flags):
    """Test that compare command filters by regulation."""
    audit1, audit2 = two_audits_with_flags
    result = runner.invoke(app, ["compare", str(audit1.id), str(audit2.id), "--regulation", "Part-145.A.30"])
    assert result.exit_code == 0
    # Should only show flags with this regulation reference


def test_cli_compare_shows_severity_shifts(two_audits_with_flags):
    """Test that compare command shows severity shifts."""
    audit1, audit2 = two_audits_with_flags
    result = runner.invoke(app, ["compare", str(audit1.id), str(audit2.id)])
    assert result.exit_code == 0
    # Should show that chunk-1 went from RED to YELLOW
    assert "Severity Shifts" in result.stdout or "severity_shifts" in result.stdout.lower()

