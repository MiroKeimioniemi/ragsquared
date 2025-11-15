"""Tests for the audits API."""

from __future__ import annotations

from backend.app.db.models import Audit, Document
from backend.app.db.session import get_session


def _seed_document(session) -> Document:
    """Create a test document."""
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
    session.commit()
    session.refresh(doc)
    return doc


def test_create_audit_success(client, app):
    """Test creating a new audit."""
    session = get_session()
    doc = _seed_document(session)

    response = client.post(
        "/audits",
        json={"document_id": doc.id, "is_draft": False},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert "audit" in data
    assert data["audit"]["document_id"] == doc.id
    assert data["audit"]["status"] == "queued"
    assert data["audit"]["is_draft"] is False


def test_create_audit_draft_mode(client, app):
    """Test creating a draft audit."""
    session = get_session()
    doc = _seed_document(session)

    response = client.post(
        "/audits",
        json={"document_id": doc.id, "is_draft": True},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["audit"]["is_draft"] is True


def test_create_audit_missing_document_id(client, app):
    """Test that missing document_id returns 400."""
    response = client.post("/audits", json={}, content_type="application/json")
    assert response.status_code == 400
    assert "document_id" in response.get_json()["error"].lower()


def test_create_audit_invalid_document(client, app):
    """Test that invalid document_id returns 404."""
    response = client.post(
        "/audits",
        json={"document_id": 99999},
        content_type="application/json",
    )
    assert response.status_code == 404


def test_get_audit_success(client, app):
    """Test retrieving an audit."""
    session = get_session()
    doc = _seed_document(session)
    audit = Audit(document_id=doc.id, status="queued", is_draft=False)
    session.add(audit)
    session.commit()
    session.refresh(audit)

    response = client.get(f"/audits/{audit.id}")
    assert response.status_code == 200
    data = response.get_json()
    assert "audit" in data
    assert data["audit"]["id"] == audit.id
    assert data["audit"]["external_id"] == audit.external_id


def test_get_audit_by_external_id(client, app):
    """Test retrieving an audit by external_id."""
    session = get_session()
    doc = _seed_document(session)
    audit = Audit(document_id=doc.id, status="queued", is_draft=False)
    session.add(audit)
    session.commit()
    session.refresh(audit)

    response = client.get(f"/audits/{audit.external_id}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["audit"]["id"] == audit.id


def test_get_audit_not_found(client, app):
    """Test that missing audit returns 404."""
    response = client.get("/audits/99999")
    assert response.status_code == 404

