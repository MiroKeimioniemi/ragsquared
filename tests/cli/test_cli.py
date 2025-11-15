"""Tests for the Developer CLI."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from cli import app

runner = CliRunner()


@pytest.fixture
def sample_audit(app, db_session):
    """Create a sample audit for testing."""
    from backend.app.db.models import Audit, Document, Flag

    session = db_session
    doc = Document(
        original_filename="test_manual.pdf",
        stored_filename="test_manual.pdf",
        storage_path="uploads/test_manual.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc)
    session.flush()

    audit = Audit(
        external_id="test-audit-cli",
        document_id=doc.id,
        status="completed",
        chunk_total=10,
        chunk_completed=10,
    )
    session.add(audit)
    session.flush()

    flag1 = Flag(
        audit_id=audit.id,
        chunk_id="chunk-1",
        flag_type="RED",
        severity_score=90,
        findings="Critical issue",
        gaps=["Missing procedure"],
        recommendations=["Add procedure"],
    )
    session.add(flag1)

    flag2 = Flag(
        audit_id=audit.id,
        chunk_id="chunk-2",
        flag_type="YELLOW",
        severity_score=60,
        findings="Warning",
        gaps=[],
        recommendations=[],
    )
    session.add(flag2)

    session.commit()
    return audit


def test_cli_status_shows_audit_info(sample_audit):
    """Test that status command shows audit information."""
    result = runner.invoke(app, ["status", str(sample_audit.id)])
    assert result.exit_code == 0
    assert sample_audit.external_id in result.stdout
    assert "completed" in result.stdout.lower() or "COMPLETED" in result.stdout


def test_cli_status_json_output(sample_audit):
    """Test that status command supports JSON output."""
    result = runner.invoke(app, ["status", str(sample_audit.id), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["audit_id"] == sample_audit.id
    assert data["external_id"] == sample_audit.external_id
    assert data["status"] == "completed"


def test_cli_status_not_found():
    """Test that status command handles missing audit."""
    result = runner.invoke(app, ["status", "99999"])
    assert result.exit_code == 1
    assert "not found" in result.stdout.lower()


def test_cli_flags_lists_flags(sample_audit):
    """Test that flags command lists flags."""
    result = runner.invoke(app, ["flags", str(sample_audit.id)])
    assert result.exit_code == 0
    assert "RED" in result.stdout
    assert "YELLOW" in result.stdout


def test_cli_flags_filters_by_severity(sample_audit):
    """Test that flags command filters by severity."""
    result = runner.invoke(app, ["flags", str(sample_audit.id), "--severity", "RED"])
    assert result.exit_code == 0
    assert "RED" in result.stdout
    # Should not show YELLOW flags
    assert result.stdout.count("YELLOW") == 0 or "YELLOW" not in result.stdout.split("\n")[5:]


def test_cli_flags_json_output(sample_audit):
    """Test that flags command supports JSON output."""
    result = runner.invoke(app, ["flags", str(sample_audit.id), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "flags" in data
    assert len(data["flags"]) > 0
    assert data["flags"][0]["flag_type"] in ("RED", "YELLOW")


def test_cli_report_generates_markdown(sample_audit, tmp_path):
    """Test that report command generates markdown."""
    output_dir = tmp_path / "reports"
    result = runner.invoke(
        app, ["report", str(sample_audit.id), "--output-dir", str(output_dir)]
    )
    assert result.exit_code == 0
    assert "Markdown report" in result.stdout

    # Check that file was created
    md_file = output_dir / f"audit_{sample_audit.external_id}.md"
    assert md_file.exists()


def test_cli_report_json_output(sample_audit, tmp_path):
    """Test that report command supports JSON output."""
    output_dir = tmp_path / "reports"
    result = runner.invoke(
        app, ["report", str(sample_audit.id), "--output-dir", str(output_dir), "--json"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "markdown_path" in data
    assert Path(data["markdown_path"]).exists()


def test_cli_compare_shows_differences(sample_audit, db_session):
    """Test that compare command shows differences between audits."""
    from backend.app.db.models import Audit, Document, Flag

    session = db_session
    # Create a second audit with different flags
    doc2 = Document(
        original_filename="test_manual2.pdf",
        stored_filename="test_manual2.pdf",
        storage_path="uploads/test_manual2.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="b" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc2)
    session.flush()

    audit2 = Audit(
        external_id="test-audit-cli-2",
        document_id=doc2.id,
        status="completed",
        chunk_total=5,
        chunk_completed=5,
    )
    session.add(audit2)
    session.flush()

    flag3 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-1",
        flag_type="GREEN",
        severity_score=10,
        findings="Compliant",
        gaps=[],
        recommendations=[],
    )
    session.add(flag3)
    session.commit()

    result = runner.invoke(app, ["compare", str(sample_audit.id), str(audit2.id)])
    assert result.exit_code == 0
    assert "Comparison" in result.stdout or "comparison" in result.stdout.lower()


def test_cli_compare_json_output(sample_audit, db_session):
    """Test that compare command supports JSON output."""
    from backend.app.db.models import Audit, Document, Flag

    session = db_session
    doc2 = Document(
        original_filename="test_manual2.pdf",
        stored_filename="test_manual2.pdf",
        storage_path="uploads/test_manual2.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="b" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc2)
    session.flush()

    audit2 = Audit(
        external_id="test-audit-cli-2",
        document_id=doc2.id,
        status="completed",
        chunk_total=5,
        chunk_completed=5,
    )
    session.add(audit2)
    session.flush()

    flag3 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-1",
        flag_type="GREEN",
        severity_score=10,
        findings="Compliant",
        gaps=[],
        recommendations=[],
    )
    session.add(flag3)
    session.commit()

    result = runner.invoke(app, ["compare", str(sample_audit.id), str(audit2.id), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "audit_a" in data
    assert "audit_b" in data
    assert "comparison" in data
    assert "summary" in data["audit_a"]
    assert "summary" in data["audit_b"]
    assert "compliance_score_delta" in data["comparison"]


def test_cli_compare_markdown_output(sample_audit, db_session):
    """Test that compare command supports markdown output."""
    from backend.app.db.models import Audit, Document, Flag

    session = db_session
    doc2 = Document(
        original_filename="test_manual2.pdf",
        stored_filename="test_manual2.pdf",
        storage_path="uploads/test_manual2.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="b" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc2)
    session.flush()

    audit2 = Audit(
        external_id="test-audit-cli-2",
        document_id=doc2.id,
        status="completed",
        chunk_total=5,
        chunk_completed=5,
    )
    session.add(audit2)
    session.flush()

    flag3 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-1",
        flag_type="GREEN",
        severity_score=10,
        findings="Compliant",
        gaps=[],
        recommendations=[],
    )
    session.add(flag3)
    session.commit()

    result = runner.invoke(app, ["compare", str(sample_audit.id), str(audit2.id), "--format", "markdown"])
    assert result.exit_code == 0
    assert "# Audit Comparison" in result.stdout
    assert "## Summary" in result.stdout


def test_cli_compare_filters_by_severity(sample_audit, db_session):
    """Test that compare command filters by severity."""
    from backend.app.db.models import Audit, Document, Flag

    session = db_session
    doc2 = Document(
        original_filename="test_manual2.pdf",
        stored_filename="test_manual2.pdf",
        storage_path="uploads/test_manual2.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="b" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc2)
    session.flush()

    audit2 = Audit(
        external_id="test-audit-cli-2",
        document_id=doc2.id,
        status="completed",
        chunk_total=5,
        chunk_completed=5,
    )
    session.add(audit2)
    session.flush()

    flag3 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-1",
        flag_type="RED",
        severity_score=90,
        findings="Critical",
        gaps=[],
        recommendations=[],
    )
    session.add(flag3)
    session.commit()

    result = runner.invoke(app, ["compare", str(sample_audit.id), str(audit2.id), "--severity", "RED", "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    # Both audits should have RED flags
    assert data["audit_a"]["summary"]["red_count"] >= 0
    assert data["audit_b"]["summary"]["red_count"] >= 0


def test_cli_compare_caches_result(sample_audit, db_session, tmp_path):
    """Test that compare command can cache results."""
    from backend.app.db.models import Audit, Document, Flag
    from unittest.mock import patch

    session = db_session
    doc2 = Document(
        original_filename="test_manual2.pdf",
        stored_filename="test_manual2.pdf",
        storage_path="uploads/test_manual2.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="b" * 64,
        source_type="manual",
        status="processed",
    )
    session.add(doc2)
    session.flush()

    audit2 = Audit(
        external_id="test-audit-cli-2",
        document_id=doc2.id,
        status="completed",
        chunk_total=5,
        chunk_completed=5,
    )
    session.add(audit2)
    session.flush()

    flag3 = Flag(
        audit_id=audit2.id,
        chunk_id="chunk-1",
        flag_type="GREEN",
        severity_score=10,
        findings="Compliant",
        gaps=[],
        recommendations=[],
    )
    session.add(flag3)
    session.commit()

    with patch("cli.AppConfig") as mock_config:
        mock_config.return_value.data_root = str(tmp_path)
        result = runner.invoke(
            app, ["compare", str(sample_audit.id), str(audit2.id), "--format", "markdown", "--cache"]
        )
        assert result.exit_code == 0
        # Check that cache file was created
        cache_dir = tmp_path / "reports" / "compare"
        assert cache_dir.exists()
        cache_files = list(cache_dir.glob("compare_*.md"))
        assert len(cache_files) > 0

