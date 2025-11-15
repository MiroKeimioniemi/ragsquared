from __future__ import annotations

import json

from backend.app.db.models import Audit, AuditorQuestion, Document, Flag, Citation
from backend.app.db.session import get_session


def _seed_audit(session) -> tuple[Audit, str]:
    doc = Document(
        external_id="doc-findings",
        original_filename="manual.md",
        stored_filename="manual.md",
        storage_path="uploads/manual.md",
        content_type="text/markdown",
        size_bytes=200,
        sha256="a" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)

    audit = Audit(document_id=doc.id, status="completed")
    session.add(audit)
    session.commit()
    session.refresh(audit)

    flag = Flag(
        audit_id=audit.id,
        chunk_id="chunk-1",
        flag_type="RED",
        severity_score=90,
        findings="Critical gap",
        gaps=["Missing reference"],
        recommendations=["Add reference"],
    )
    flag.citations.append(Citation(citation_type="manual", reference="Section 1"))
    flag.citations.append(Citation(citation_type="regulation", reference="Part-145.A.30"))
    session.add(flag)
    session.commit()

    return audit, audit.external_id


def test_list_flags_returns_results(client, app):
    session = get_session()
    audit, audit_external = _seed_audit(session)

    response = client.get(f"/audits/{audit_external}/flags")
    assert response.status_code == 200
    data = response.get_json()
    assert data["audit"]["id"] == audit.id
    assert len(data["flags"]) == 1
    assert data["flags"][0]["flag_type"] == "RED"


def test_list_flags_filters_by_severity(client, app):
    session = get_session()
    audit, audit_external = _seed_audit(session)

    response = client.get(f"/audits/{audit_external}/flags?severity=green")
    assert response.status_code == 200
    assert response.get_json()["flags"] == []


def test_list_flags_missing_audit(client):
    response = client.get("/audits/unknown/flags")
    assert response.status_code == 404


def test_list_flags_includes_questions(client, app):
    session = get_session()
    audit, audit_external = _seed_audit(session)

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

    response = client.get(f"/audits/{audit_external}/flags?include_questions=1")
    assert response.status_code == 200
    data = response.get_json()
    assert "questions" in data
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question_text"] == "Test question?"


def test_list_flags_excludes_questions_by_default(client, app):
    session = get_session()
    audit, audit_external = _seed_audit(session)

    question = AuditorQuestion(
        audit_id=audit.id,
        regulation_reference="Part-145.A.30",
        question_text="Test question?",
        priority=1,
        rationale="Test rationale",
    )
    session.add(question)
    session.commit()

    response = client.get(f"/audits/{audit_external}/flags")
    assert response.status_code == 200
    data = response.get_json()
    assert "questions" not in data

