from __future__ import annotations

from pathlib import Path

from backend.app.db.models import Audit, AuditorQuestion, Document, Flag, Citation
from backend.app.db.session import get_session
from backend.app.reports.generator import ReportGenerator, ReportRequest


def _seed_flags(session) -> Audit:
    doc = Document(
        original_filename="manual.md",
        stored_filename="manual.md",
        storage_path="uploads/manual.md",
        content_type="text/markdown",
        size_bytes=500,
        sha256="f" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    audit = Audit(document_id=doc.id, status="completed", chunk_total=2, chunk_completed=2)
    session.add(audit)
    session.commit()
    session.refresh(audit)

    flag = Flag(
        audit_id=audit.id,
        chunk_id="chunk-1",
        flag_type="RED",
        severity_score=85,
        findings="Critical gap",
        gaps=["Missing procedure"],
        recommendations=["Add procedure"],
    )
    flag.citations.append(Citation(citation_type="manual", reference="Section 1"))
    session.add(flag)
    session.commit()

    return audit


def test_report_generator_writes_markdown(tmp_path: Path, app):
    session = get_session()
    audit = _seed_flags(session)
    output_dir = tmp_path / "reports"

    generator = ReportGenerator(output_dir)
    report_path = generator.render_markdown(ReportRequest(audit_id=audit.id))

    assert report_path.exists()
    content = report_path.read_text(encoding="utf-8")
    assert "Audit Report" in content
    assert "Critical gap" in content


def test_report_generator_includes_questions(tmp_path: Path, app):
    session = get_session()
    audit = _seed_flags(session)

    # Add a question
    question = AuditorQuestion(
        audit_id=audit.id,
        regulation_reference="Part-145.A.30",
        question_text="Test question?",
        priority=1,
        rationale="Test rationale",
    )
    session.add(question)
    session.commit()

    output_dir = tmp_path / "reports"
    generator = ReportGenerator(output_dir)
    report_path = generator.render_markdown(ReportRequest(audit_id=audit.id))

    content = report_path.read_text(encoding="utf-8")
    assert "Auditor Questions" in content
    assert "Test question?" in content
    assert "Test rationale" in content


def test_report_generator_shows_draft_status(tmp_path: Path, app):
    """Test that report generator shows draft status."""
    session = get_session()
    audit = _seed_flags(session)
    audit.is_draft = True
    session.commit()

    output_dir = tmp_path / "reports"
    generator = ReportGenerator(output_dir)
    report_path = generator.render_markdown(ReportRequest(audit_id=audit.id))

    content = report_path.read_text(encoding="utf-8")
    assert "DRAFT" in content or "draft" in content.lower()
    assert "Limited processing" in content or "reduced chunks" in content.lower()

